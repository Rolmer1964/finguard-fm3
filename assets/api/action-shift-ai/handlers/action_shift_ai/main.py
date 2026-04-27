import concurrent.futures
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple

from commons.constants import CODE_SHIFT_PULL_REQUEST_FILE_PATH, CODE_SHIFT_PULL_REPORT_PATH
from commons.services.ai import AiServices
from commons.services.analytics import FileAnalyticsServices
from commons.services.entities.agent import Agent
from commons.services.entities.external_agent import ExternalAgent
from commons.services.entities.project_file_knowledge_source import ProjectFileKnowledgeSource
from commons.services.entities.quick_command import QuickCommand
from commons.services.file import FileServices, FileSelectionService
from commons.services.git import Git
from commons.services.json_utils import loads_json_with_sanitization
from commons.stk.stackspot_http_client import StackspotHttpClient
from handlers.action_shift_ai.prompts import custom_agent_flow
from handlers.action_shift_ai.prompts import custom_agent_flow_with_prompt
from handlers.action_shift_ai.prompts import default_agent_flow

logger = logging.getLogger()
SHIFT_AI_AGENT_SLUG = "shift-ai-agent"
SHIFT_AI_PREFIX = "shift-ai-ks"
MAX_APP_NAME_LENGTH = 33
SHIFT_AI_SYSTEM_PROMPT = "Você é um agente de refatoração de código. Retorne somente JSON válido no formato solicitado pelo usuário."
file_analytics_service = FileAnalyticsServices()
stackspot_http_client = StackspotHttpClient()
ai_services = AiServices(stackspot_http_client=stackspot_http_client)

EXTENSION_TO_LANGUAGE = {
    '.py': 'python',
    '.java': 'java',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.c': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
    '.h': 'cpp',
    '.cs': 'csharp',
    '.go': 'go',
    '.rb': 'ruby',
    '.php': 'php',
    '.kt': 'kotlin',
    '.kts': 'kotlin',
    '.swift': 'swift',
    '.rs': 'rust',
    '.scala': 'scala',
    '.sh': 'shell'
}


@dataclass(frozen=True)
class ExecutionConfig:
    max_workers: int = 5
    rate_limit_delay: float = 0.2


@dataclass(frozen=True)
class BaseFlowContext:
    app_name: str
    path_filter: str
    selected_files: list[dict]
    module_inputs: dict


@dataclass(frozen=True)
class AgentFlowContext:
    base: BaseFlowContext
    conversation_id: str | None
    delete_agent: bool
    delete_ks: bool
    prompt_template: str


def get_language_from_path(path: str) -> Optional[str]:
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def process_prompts_parallel(
        agent: Agent,
        prompts: list[dict],
        max_workers: int = 5,
        rate_limit_delay: float = 0.2,
) -> dict[tuple[str, str], Any]:
    def call_wrapper(item: dict) -> tuple[tuple[str, str], Any]:
        if rate_limit_delay and rate_limit_delay > 0:
            time.sleep(rate_limit_delay)
        response = agent.chat(prompt=item["prompt"])
        return (item["target_path"], item["original_content"]), response

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(call_wrapper, prompts)

    return dict(results)


def process_rqc_parallel(
        qc: QuickCommand,
        prompts: list[dict],
        max_workers: int = 5,
        rate_limit_delay: float = 0.2,
) -> dict[tuple[str, str], Any]:
    def call_wrapper(item: dict) -> tuple[tuple[str, str], Any]:
        if rate_limit_delay and rate_limit_delay > 0:
            time.sleep(rate_limit_delay)
        response = qc.execute(
            input_data={
                'path': item["target_path"],
                'content': item["original_content"]
            }
        )
        return (item["target_path"], item["original_content"]), response

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(call_wrapper, prompts)

    return dict(results)


def _parse_agent_response(response: Any, fallback_path: str) -> Optional[dict]:
    try:
        if isinstance(response, dict):
            data = response
        elif isinstance(response, str):
            data = loads_json_with_sanitization(response)
        else:
            logger.warning(f"Tipo de resposta não suportado: {type(response)}")
            return None

        if not isinstance(data, dict):
            logger.warning("Resposta não é um dicionário JSON válido")
            return None

        if 'path' not in data:
            data['path'] = fallback_path

        return data

    except json.JSONDecodeError as exc:
        logger.error(f"Erro ao fazer parse do JSON: {exc}")
        logger.info(f"Resposta recebida: {str(response)[:200]}...")
        return None
    except Exception as exc:
        logger.error(f"Erro inesperado ao processar resposta: {exc}")
        return None


def _extract_update_from_agent_response(
        response: Any,
        fallback_path: str,
        original_content: str,
        agent_slug: str,
) -> Optional[Tuple[str, str, str]]:
    data = _parse_agent_response(response=response, fallback_path=fallback_path)

    if data is None:
        return None

    actual_path = data.get('path', fallback_path)
    content = data.get('content', '')

    if not isinstance(content, str) or not content.strip():
        logger.info(f"Pulando arquivo com conteúdo vazio: {actual_path}")
        return None

    if content.strip() == original_content.strip():
        logger.info(f"Pulando arquivo com conteúdo idêntico ao original: {actual_path}")
        return None

    reason = data.get('reason', f"Processado via Agent \"{agent_slug or 'unknown'}\"")
    return actual_path, content, reason


def _try_parse_malformed_rqc_result(raw_result: str) -> Optional[dict]:
    marker = '","tokens":'
    code_prefix = '"code":"'

    code_start = raw_result.find(code_prefix)
    tokens_start = raw_result.rfind(marker)

    if code_start == -1 or tokens_start == -1 or tokens_start <= code_start:
        return None

    code_value_start = code_start + len(code_prefix)
    code_value_raw = raw_result[code_value_start:tokens_start]
    tokens_raw = raw_result[tokens_start + len(marker):].strip()

    while code_value_raw.endswith('\\n') or code_value_raw.endswith('\\r'):
        code_value_raw = code_value_raw[:-2]

    if tokens_raw.endswith('}'):
        tokens_raw = tokens_raw[:-1]

    try:
        code_data = json.loads(code_value_raw)
        tokens_data = json.loads(tokens_raw)
    except json.JSONDecodeError:
        return None

    return {
        'code': code_data,
        'tokens': tokens_data,
    }


def _parse_rqc_response(response: Any, fallback_path: str) -> Optional[dict]:
    try:
        if isinstance(response, str):
            parsed_response = None
            try:
                parsed_response = loads_json_with_sanitization(response)
            except json.JSONDecodeError:
                parsed_response = _try_parse_malformed_rqc_result(response)

            if parsed_response is None:
                logger.error("Erro ao parsear response como JSON")
                return None

            response = parsed_response

        if not isinstance(response, dict):
            logger.warning(f"Response não é dict nem string: {type(response)}")
            return None

        if 'code' not in response:
            logger.error("Campo 'code' ausente no response do RQC")
            return None

        code_data = response.get('code')

        if isinstance(code_data, str):
            try:
                code_data = json.loads(code_data)
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao parsear campo 'code' como JSON: {e}")
                return None

        if not isinstance(code_data, dict):
            logger.error(f"Campo 'code' não é dict: {type(code_data)}")
            return None

        operation = code_data.get('operation', 'update').lower()
        if operation not in ['create', 'update']:
            logger.warning(f"Operação inválida '{operation}', usando 'update'")
            operation = 'update'

        source_file = code_data.get('source_file', fallback_path)
        target_file = code_data.get('target_file', source_file)
        answer = code_data.get('answer', '').strip()
        reason = code_data.get('reason', '')
        tokens = response.get('tokens', {})

        if not answer:
            logger.warning("Campo 'answer' vazio no response")
            return None

        return {
            'operation': operation,
            'source_file': source_file,
            'target_file': target_file,
            'answer': answer,
            'reason': reason,
            'tokens': tokens
        }

    except Exception as e:
        logger.error(f"Erro inesperado ao parsear response: {e}", exc_info=True)
        return None


def _extract_update_from_rqc_response(
        response: Any,
        fallback_path: str,
        original_content: str,
        rqc_slug: str,
        base_directory: str,
) -> Optional[Tuple[str, str, str, str]]:
    data = _parse_rqc_response(response=response, fallback_path=fallback_path)
    if data is None:
        return None

    operation = data.get('operation', 'update')
    target_file = data.get('target_file', fallback_path)
    target_path = target_file if os.path.isabs(target_file) else os.path.join(base_directory, target_file)
    new_content = data.get('answer', '')

    if operation == 'update' and new_content.strip() == original_content.strip():
        logger.info(f"[RQC] Pulando conteúdo idêntico ao original: {target_path}")
        return None

    if operation == 'create' and data.get('source_file') == data.get('target_file'):
        logger.warning(f"[RQC] Create com source_file == target_file ignorado: {target_path}")
        return None

    reason = data.get('reason') or f"[RQC] Processado via \"{rqc_slug or 'unknown'}\" (operation: {operation})"
    return target_path, new_content, reason, operation


def build_report_data(directory: str, files_created: dict) -> dict:
    target_files = [
        {
            "fileName": os.path.basename(file_path),
            "filePath": os.path.relpath(os.path.dirname(file_path) or '.', start=directory),
            "details": content,
            "dependsOn": [],
            "issues": []
        }
        for file_path, content in files_created.items()
    ]
    return {"target_files": target_files}


def build_pr_data(directory: str, files_created: dict) -> dict:
    files_relative = {
        os.path.relpath(file_path, start=directory): content
        for file_path, content in files_created.items()
    }
    return {
        "module": "shift-ai",
        "pull_request_text": "Mudanças de código aplicadas via action-shift-ai",
        "deleted_files": [],
        "files": files_relative,
    }


def _select_files(
        files_filter: str,
        files_filter_text: Optional[str],
        json_tree: str
) -> List[Dict]:
    processor = FileSelectionService(
        json_tree=json_tree,
        files_filter=files_filter,
        files_filter_text=files_filter_text
    )

    selected_files = json.loads(processor.run())
    return selected_files


def _select_prompt_template(agent_id: Optional[str], prompt: Optional[str]) -> str:
    if agent_id and prompt:
        return custom_agent_flow_with_prompt.prompt

    if agent_id:
        return custom_agent_flow.prompt

    raise ValueError("Para how_to_change Agent é necessário informar agent_id.")


def _prepare_agent_prompts(
        selected_files,
        path_filter: str,
        prompt_template: str,
        prompt: str,
) -> list[dict]:
    prompts_to_process = []

    for item in selected_files:
        file_path = item.get("path")
        file_name = item.get("name") or os.path.basename(file_path)
        normalized_path = file_path if os.path.isabs(file_path) else os.path.join(path_filter, file_path)
        file_content = FileServices.read_file(normalized_path) or ""
        file_lang = get_language_from_path(path=file_path) or 'code'

        full_prompt = prompt_template.format(
            file_path=file_path,
            file_name=file_name,
            file_lang=file_lang,
            content=file_content,
            user_prompt=prompt or ""
        )

        prompts_to_process.append({
            "target_path": normalized_path,
            "original_content": file_content,
            "prompt": full_prompt
        })

    return prompts_to_process


def _process_and_persist_agent_updates(
        processed_results: dict[tuple[str, str], Any],
        agent_slug: str,
) -> dict:
    logger.info("Salvando arquivos processados...")
    files_created = {}

    for (fallback_path, original_content), response in processed_results.items():
        parsed = _extract_update_from_agent_response(
            response=response,
            fallback_path=fallback_path,
            original_content=original_content,
            agent_slug=agent_slug
        )

        if not parsed:
            continue

        target_path, new_content, reason = parsed
        save_result = FileServices.save_or_update_file(target_path, new_content)
        if isinstance(save_result, dict) and save_result.get("status") != "success":
            logger.error(f"Erro ao salvar arquivo {target_path}: {save_result.get('error')}")
            continue

        files_created[target_path] = new_content
        logger.info(f"Arquivo atualizado: {target_path} | Motivo: {reason}")

    logger.info(f"Total de {len(files_created)} arquivos salvos no caminho original.")
    return files_created


def _save_shift_outputs(directory: str, files_created: dict) -> tuple[dict, dict]:
    report_data = build_report_data(directory=directory, files_created=files_created)
    pr_data = build_pr_data(directory=directory, files_created=files_created)

    FileServices.save_json_file(
        file_path=CODE_SHIFT_PULL_REPORT_PATH,
        data=report_data
    )
    logger.info(f"Report salvo em {CODE_SHIFT_PULL_REPORT_PATH}")

    FileServices.save_json_file(
        file_path=CODE_SHIFT_PULL_REQUEST_FILE_PATH,
        data=pr_data
    )
    logger.info(f"Pull Request data salvo em {CODE_SHIFT_PULL_REQUEST_FILE_PATH}")
    logger.info("action-shift-ai finalizado com sucesso!")

    return report_data, pr_data


def _find_project_root(start_path: str) -> str:
    current = Path(start_path).resolve()

    root_markers = {'.git', 'pyproject.toml', 'setup.py', 'package.json', 'pom.xml', 'Cargo.toml'}

    while current != current.parent:
        if any((current / marker).exists() for marker in root_markers):
            logger.info(
                f"Raiz do projeto encontrada: {current} (marcador: {[m for m in root_markers if (current / m).exists()][0]})")
            return str(current)
        current = current.parent

    fallback = os.getcwd()
    logger.warning(f"Nenhum marcador de raiz encontrado, usando diretório atual: {fallback}")
    return fallback


def _prompt_agent_flow(
        agent_flow_context: AgentFlowContext,
        execution: ExecutionConfig,
) -> tuple[dict, dict]:
    context = agent_flow_context.base
    prompt = context.module_inputs.get('prompt') or ""
    path_filter_absolute = os.path.abspath(context.path_filter)
    project_root = _find_project_root(path_filter_absolute)

    logger.info(f"Iniciando mudança de código para {context.app_name}")

    logger.info("Criando Knowledge Source e indexando arquivos...")
    logger.info(f"KS Slug será: {SHIFT_AI_PREFIX}-{context.app_name}-{agent_flow_context.conversation_id}")
    with ProjectFileKnowledgeSource(
            slug=f"{SHIFT_AI_PREFIX}-{context.app_name}-{agent_flow_context.conversation_id}".lower(),
            description=f"Base de conhecimento para mudança de código em {context.app_name}",
            directory=context.path_filter,
            delete_ks=agent_flow_context.delete_ks,
            ai_services=ai_services,
    ) as ks:
        logger.info(f"Knowledge Source criado: {ks.ks_id}")

        agent_slug = f"{SHIFT_AI_AGENT_SLUG}-{agent_flow_context.conversation_id}".lower()
        with Agent(
                slug=agent_slug,
                system_prompt=SHIFT_AI_SYSTEM_PROMPT,
                ai_services=ai_services,
                delete_agent=agent_flow_context.delete_agent,
                ks_ids=[ks.ks_id],
        ) as main_agent:
            logger.info("Agente principal criado. Preparando prompts...")

            prompts_to_process = _prepare_agent_prompts(
                selected_files=context.selected_files,
                path_filter=context.path_filter,
                prompt_template=agent_flow_context.prompt_template,
                prompt=prompt,
            )
            logger.info(f"Processando {len(prompts_to_process)} prompts em paralelo...")
            processed_results = process_prompts_parallel(
                agent=main_agent,
                prompts=prompts_to_process,
                max_workers=execution.max_workers,
                rate_limit_delay=execution.rate_limit_delay,
            )
            logger.info(f"Respostas recebidas para {len(processed_results)} arquivos.")

            files_created = _process_and_persist_agent_updates(
                processed_results=processed_results,
                agent_slug=agent_slug,
            )

    return _save_shift_outputs(directory=project_root, files_created=files_created)


def _custom_agent_flow(
        context: BaseFlowContext,
        prompt_template: str,
        conversation_id: str | None,
        execution: ExecutionConfig,
) -> tuple[dict, dict]:
    agent_id = context.module_inputs.get('agent_id')
    prompt = context.module_inputs.get('prompt') or ""
    path_filter_absolute = os.path.abspath(context.path_filter)
    project_root = _find_project_root(path_filter_absolute)

    if not agent_id:
        raise ValueError("Para how_to_change Agent é necessário informar agent_id.")

    logger.info(f"Iniciando mudança de código com agente externo para {context.app_name}")

    with ExternalAgent(
            agent_id=agent_id,
            ai_services=ai_services,
            conversation_id=conversation_id,
    ) as main_agent:
        logger.info("Agente externo carregado. Preparando prompts...")

        prompts_to_process = _prepare_agent_prompts(
            selected_files=context.selected_files,
            path_filter=context.path_filter,
            prompt_template=prompt_template,
            prompt=prompt,
        )
        logger.info(f"Processando {len(prompts_to_process)} prompts em paralelo...")
        processed_results = process_prompts_parallel(
            agent=main_agent,
            prompts=prompts_to_process,
            max_workers=execution.max_workers,
            rate_limit_delay=execution.rate_limit_delay,
        )
        logger.info(f"Respostas recebidas para {len(processed_results)} arquivos.")

        files_created = _process_and_persist_agent_updates(
            processed_results=processed_results,
            agent_slug=agent_id,
        )

    return _save_shift_outputs(directory=project_root, files_created=files_created)


def _rqc_flow(
        context: BaseFlowContext,
        execution: ExecutionConfig,
) -> tuple[dict, dict]:
    slug_rqc = context.module_inputs.get('slug_rqc')
    if not slug_rqc:
        raise ValueError("Para how_to_change RQC é necessário informar slug_rqc.")

    path_filter_absolute = os.path.abspath(context.path_filter)
    logger.info(f"Path filter normalizado: {context.path_filter} → {path_filter_absolute}")

    project_root = _find_project_root(path_filter_absolute)
    logger.info(f"Raiz do projeto identificada: {project_root}")

    logger.info(f"Iniciando mudança de código via RQC para {context.app_name}")

    qc = QuickCommand(slug=slug_rqc, ai_services=ai_services, validate_response=False)

    prompts_to_process = []
    for item in context.selected_files:
        file_path = item.get("path")
        normalized_path = file_path if os.path.isabs(file_path) else os.path.join(path_filter_absolute, file_path)
        file_content = FileServices.read_file(normalized_path) or ""

        prompts_to_process.append({
            "target_path": normalized_path,
            "original_content": file_content,
        })

    logger.info(f"Processando {len(prompts_to_process)} execuções RQC em paralelo...")
    processed_results = process_rqc_parallel(
        qc=qc,
        prompts=prompts_to_process,
        max_workers=execution.max_workers,
        rate_limit_delay=execution.rate_limit_delay,
    )
    logger.info(f"Respostas recebidas para {len(processed_results)} arquivos.")

    files_created = {}
    for (fallback_path, original_content), response in processed_results.items():
        parsed = _extract_update_from_rqc_response(
            response=response,
            fallback_path=fallback_path,
            original_content=original_content,
            rqc_slug=slug_rqc,
            base_directory=project_root,
        )

        if not parsed:
            continue

        target_path, new_content, reason, operation = parsed

        logger.info(f"Path resolution: {operation} → {target_path}")

        save_result = FileServices.save_or_update_file(target_path, new_content)
        if isinstance(save_result, dict) and save_result.get("status") != "success":
            logger.error(f"Erro ao salvar arquivo {target_path}: {save_result.get('error')}")
            continue

        files_created[target_path] = new_content
        logger.info(f"Arquivo {operation}d: {target_path} | Motivo: {reason}")

    logger.info(f"Total de {len(files_created)} arquivos persistidos via RQC.")

    return _save_shift_outputs(directory=project_root, files_created=files_created)


def main(
        module_inputs: dict = None,
        conversation_id: str = None,
        delete_agent: bool = True,
        delete_ks: bool = True
):
    logger.info("Iniciando processo...")

    module_inputs = module_inputs or {}

    how_to_change = module_inputs.get('how_to_change') or 'Prompt'

    path_filter = module_inputs.get('path_filter') or "."
    files_filter = module_inputs.get('files_filter') or "*.*"
    files_filter_text = module_inputs.get('files_filter_text') or []
    max_workers = module_inputs.get('max_workers', 5)
    rate_limit_delay = module_inputs.get('rate_limit_delay', 0.2)

    FileServices.validate_directory(directory=path_filter)
    app_name_slug = Git.get_repo_name(directory=path_filter)
    app_name = app_name_slug[:MAX_APP_NAME_LENGTH]

    logger.info("Analisando estrutura do projeto...")
    json_tree = file_analytics_service.generate_json_tree(path=path_filter)
    logger.info(f"Estrutura analisada. Total de Arquivos: {len(json_tree)}")

    selected_files = _select_files(
        files_filter=files_filter,
        files_filter_text=files_filter_text,
        json_tree=json_tree
    )

    base_context = BaseFlowContext(
        app_name=app_name,
        path_filter=path_filter,
        selected_files=selected_files,
        module_inputs=module_inputs,
    )

    execution = ExecutionConfig(
        max_workers=max_workers,
        rate_limit_delay=rate_limit_delay,
    )

    if how_to_change == 'Prompt':
        context = AgentFlowContext(
            base=base_context,
            conversation_id=conversation_id,
            delete_agent=delete_agent,
            delete_ks=delete_ks,
            prompt_template=default_agent_flow.prompt,
        )
        return _prompt_agent_flow(
            agent_flow_context=context,
            execution=execution
        )

    elif how_to_change == 'Agent':
        prompt_template = _select_prompt_template(
            agent_id=module_inputs.get('agent_id'),
            prompt=module_inputs.get('prompt')
        )
        return _custom_agent_flow(
            context=base_context,
            execution=execution,
            conversation_id=conversation_id,
            prompt_template=prompt_template,
        )

    elif how_to_change == 'RQC':
        return _rqc_flow(
            context=base_context,
            execution=execution
        )

    return None
