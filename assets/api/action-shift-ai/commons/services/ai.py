import concurrent.futures
import json
import os
import re
import time
from logging import getLogger
from typing import Optional, List

import requests

from commons.stk.http.ai.agent import Agent
from commons.stk.http.ai.ks import KnowledgeSource
from commons.stk.http.ai.qc import QuickCommand
from commons.stk.stackspot_http_client import StackspotHttpClient

logger = getLogger()


class AiServices:
    def __init__(self, stackspot_http_client: StackspotHttpClient):
        self.stackspot_http_client = stackspot_http_client
        self._agent = Agent(self.stackspot_http_client)
        self._ks = KnowledgeSource(self.stackspot_http_client)
        self._qc = QuickCommand(self.stackspot_http_client)

    def get_knowledge_source(self, ks_slug: str):
        return self._ks.get_by_slug(ks_slug=ks_slug)

    def _get_ks_id_by_slug(self, slug: str) -> str | None:
        """Helper to find a KS ID by slug from the list."""
        all_ks = self._ks.get_all_ks()
        logger.info(f"'all_ks' Response: {all_ks}")
        for ks in all_ks:
            if ks["slug"] == slug:
                logger.info(f"KS {slug} encontrado.")
                return ks["id"]
        return None

    def create_knowledge_source(self, ks_slug: str, name: str, description: str, type: str, on_conflict_delete: bool = False, **kwargs):
        try:
            ks = self._get_ks_id_by_slug(ks_slug)
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 404:
                ks = None
            else:
                raise err
        if on_conflict_delete and ks:
            self._ks.delete(ks_slug=ks_slug)
        if not on_conflict_delete and ks:
            return ks["id"]
        create_result = self._ks.create(
            slug=ks_slug,
            name=name,
            description=description,
            type=type,
            **kwargs
        )
        logger.info(f"Create result: {create_result}")
        return self._get_ks_id_by_slug(ks_slug)

    def delete_knowledge_source(self, ks_slug: str):
        self._ks.delete(ks_slug=ks_slug)

    def create_agent(
        self,
        name: str,
        slug: str,
        system_prompt: str,
        on_conflict_delete: bool = False,
        ks_ids: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        agents = self._agent.list_agents(visibility_list="personal", slug=slug) or dict()
        print("List agents result: {agents}".format(agents=agents))
        for agent in agents.get("items", []):
            if slug == agent["slug"]:
                if on_conflict_delete:
                    self._agent.delete(agent_id=agent["id"])
        agent = self._agent.create(name=name, slug=slug, system_prompt=system_prompt, ks_ids=ks_ids, **kwargs)
        return agent['id']

    def call_agent(self, agent_id: str, prompt: str, **kwargs):
        return self._agent.chat(
            agent_id=agent_id,
            prompt=prompt,
            **kwargs
        )

    def delete_agent(self, agent_id: str):
        self._agent.delete(agent_id=agent_id)

    def multi_upload_knowledge_source(self, ks_slug: str, zip_file: str):
        ids_upload = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_upload = {
                executor.submit(
                    self.upload_knowledge_source, ks_slug, os.path.basename(file_path), file_path
                ): file_path for file_path in zip_file
            }
            for future in concurrent.futures.as_completed(future_to_upload):
                try:
                    result = future.result()
                    ids_upload.append(result)
                except Exception as exc:
                    logger.info(f"Gerou uma exceção no paralelismo de upload: {exc}")
        return ids_upload

    def upload_knowledge_source(self, ks_slug: str, file_name: str, file_path: str):
        upload_info = self._ks.get_upload_url(file_name, ks_slug, "KNOWLEDGE_SOURCE", 600)
        self._ks.upload_file(upload_info['url'], file_path, upload_info['form'])
        # self._ks.split_upload_file(upload_info['id'])
        self._ks.index_upload_file(upload_info['id'])
        self.wait_until_indexed(upload_info['id'])
        return upload_info['id']

    def wait_until_indexed(self, upload_id):
        max_attempts = 50
        attempts = 0
        status = self._ks.check_upload_status(upload_id)
        while status['status'] != "INDEXED" and attempts < max_attempts:
            if status['status'] in ["ERROR", "SPLIT_ERROR"]:
                error_message = f"Erro encontrado: {status['summary']['errors']}\n"
                logger.info(error_message)
                with open("log_erros.txt", "a", encoding='utf-8') as log_file:
                    log_file.write(error_message)
                break
            logger.info(
                f"Id: {upload_id} | Tentativa: {attempts + 1} | Status atual: {status['status']}. Aguardando...")
            time.sleep(10)

            status = self._ks.check_upload_status(upload_id)
            attempts += 1

        if status['status'] == "INDEXED":
            logger.info("Status final: INDEXED")
        elif status['status'] in ["ERROR", "SPLIT_ERROR"]:
            error_message = f"Erro final: {status['summary']['errors']}\n"
            logger.info(error_message)
            with open("log_erros.txt", "a", encoding='utf-8') as log_file:
                log_file.write(error_message)
        else:
            logger.info("Número máximo de tentativas atingido. Status não foi INDEXED.")

        return status['status']

    def translate_json_response_message(self, response: str):
        try:
            raw_text = response

            if not raw_text:
                print("Aviso: response vazia.")
                return None

            # 2. Localizar os limites do JSON
            # Encontra a PRIMEIRA chave de abertura
            idx_inicio = raw_text.find('{')
            # Encontra a ÚLTIMA chave de fechamento
            idx_fim = raw_text.rfind('}')

            if idx_inicio == -1 or idx_fim == -1 or idx_inicio > idx_fim:
                raise ValueError("Não foi possível localizar um bloco JSON válido (par de chaves {}).")

            # 3. Extração Cirúrgica
            # Pegamos tudo que está ENTRE a primeira e a última chave (inclusive elas).
            # Isso descarta automaticamente o "```json" (que está antes) e o "```" (que está depois).
            json_candidate = raw_text[idx_inicio: idx_fim + 1]

            # 4. Tratamento de Chaves Duplas {{ ... }}
            # Aplicamos a correção apenas no candidato extraído
            if json_candidate.startswith("{{") and json_candidate.endswith("}}"):
                json_candidate = json_candidate[1:-1]

            # 5. Limpeza de Caracteres de Controle (Preservando conteúdo)
            # Remove apenas controles perigosos, mantendo Tab, NewLine e Return
            # Isso garante que se houver código dentro do JSON, as quebras de linha sejam mantidas.
            json_candidate = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_candidate)

            # 6. Parse
            dados = json.loads(json_candidate)

            # 7. Retorno do conteúdo específico ou do objeto todo
            if isinstance(dados, dict) and "content" in dados:
                return {"content": dados["content"]}

            return dados

        except json.JSONDecodeError as e:
            print(f"⚠️ Erro ao decodificar JSON: {e}")
            # Debug: mostra o início do texto que tentamos ler para facilitar a correção
            print(f'TRECHO FALHO: {raw_text[idx_inicio:idx_inicio + 50]}...')
            raise e
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            print('RESPOSTA ORIGINAL:', response)
            raise e
