import fnmatch
import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Optional, Union, Sequence, List, Dict, Any

TMP_DIR = "/tmp"
allowed_ext = [
    "abap", "ada", "adb", "ads", "aes", "cls", "azcli", "bat", "cmd", "bicep", "c", "h", "cs", "cpp", "cc", "cxx", "hpp",
    "hxx", "hh", "mligo", "clj", "cljs", "cljc", "edn", "cob", "cbl", "coffee", "csp", "css", "d", "dart", "dockerfile",
    "ecl", "ex", "exs", "erl", "hrl", "fs", "fsi", "flow", "f90", "f", "for", "f77", "ftl", "go", "graphql", "gql",
    "groovy", "gvy", "gy", "gsh", "handlebars", "hbs", "hs", "hcl", "tf", "html", "htm", "ini", "java", "js", "mjs",
    "jsx", "json", "jl", "kt", "kts", "less", "lex", "liquid", "lua", "m3", "md", "dax", "asm", "m", "ml", "mli",
    "octave", "pas", "pp", "ligo", "pl", "pm", "php", "pla", "txt", "dats", "sats", "hats", "pq", "ps1", "psm1",
    "psd1", "prg", "proto", "pug", "py", "qs", "r", "rkt", "cshtml", "redis", "rego", "rst", "rb", "rs", "sb",
    "lisp", "scala", "scm", "scss", "sh", "sol", "rq", "sql", "st", "swift", "sv", "tcl", "twig", "ts", "tsx",
    "vb", "v", "xml", "yaml", "yml"
]

logger = logging.getLogger(__name__)


class FileServices:

    @staticmethod
    def count_file_lines(file_path: str) -> int:
        with open(file_path, 'rb') as f:
            return sum(1 for _ in f)

    @staticmethod
    def gen_zip_from_dir(directory: str, max_size: int):
        arquivos_zip = []
        zip_num = 1
        linhas_atuais = 0
        zip_path = os.path.join(TMP_DIR, f"part{zip_num}.zip")
        print('--------------------')
        print('Criando ZIP', zip_path)
        zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)

        FORBIDDEN = {"tmp", "node_modules", "dist", "build", ".git"}

        for root, dirs, files in os.walk(directory):
            print(f'os.walk root={root}')
            dirs[:] = [d for d in dirs if d.lower() not in FORBIDDEN]
            for file in files:
                print(f'Iniciando file: {file}')
                # Verifica extensão
                extensao = os.path.splitext(file)[1].lower().replace(".", "")
                if extensao not in allowed_ext:
                    print(f"Pulando arquivo ignorado: {file}")
                    continue

                file_path = os.path.join(root, file)
                caminho_arquivo = file_path

                if os.name == 'nt':
                    caminho_arquivo = os.path.normpath(file_path)
                    if len(caminho_arquivo) >= 260:
                        file_path = f"\\\\?\\{caminho_arquivo}"

                caminho_relativo = os.path.relpath(caminho_arquivo, directory)

                # Alterar extensões conforme necessário
                if file.endswith(".data"):
                    caminho_relativo = caminho_relativo.replace(".data", ".cbl")
                elif file.endswith(".tfvars"):
                    caminho_relativo = caminho_relativo.replace(".tfvars", ".tf")

                if os.path.exists(file_path):
                    linhas_arquivo = FileServices.count_file_lines(file_path=file_path)
                else:
                    raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

                if linhas_atuais + linhas_arquivo > max_size:
                    zipf.close()
                    arquivos_zip.append(zip_path)
                    zip_num += 1
                    zip_path = os.path.join(TMP_DIR, f"part{zip_num}.zip")
                    zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
                    linhas_atuais = 0

                zipf.write(file_path, caminho_relativo)
                linhas_atuais += linhas_arquivo

                print(f'Finalizando file: {file}')

        zipf.close()
        arquivos_zip.append(zip_path)
        return arquivos_zip

    @staticmethod
    def delete(file: str):
        print(f"[DELETE] {file}")
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"[DELETE] Arquivo removido: {file}")
            else:
                print(f"[DELETE] Arquivo não encontrado: {file}")
        except Exception as e:
            print(f"[DELETE] Erro ao deletar {file}: {e}")

    @staticmethod
    def save_or_update_file(file: str, content: str):
        try:
            dir_path = os.path.dirname(file)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            mode = "w"
            with open(file, mode, encoding="utf-8") as f:
                f.write(content)

            if os.path.exists(file):
                print(f"[SAVE] Arquivo criado/atualizado: {file}")

            return {"status": "success", "file": file}

        except Exception as e:
            print(f"[SAVE] Erro ao salvar {file}: {e}")
            return {"status": "error", "file": file, "error": str(e)}

    @staticmethod
    def save_json_file(file_path: str, data: dict):
        try:
            json_path = os.path.join(TMP_DIR, file_path)
            with open(json_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving JSON file {file_path}: {e}")

    @staticmethod
    def validate_directory(directory: str):
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            raise Exception(f"Diretório {directory} está inválido")

    @staticmethod
    def read_file(file_path: str):
        if os.name == 'nt':
            file_path = os.path.normpath(file_path)
            if len(file_path) > 260:
                file_path = f"\\\\?\\{file_path}"

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='iso-8859-1') as file:
                    return file.read()
        else:
            return None


class FileSelectionService:
    def __init__(
            self,
            json_tree: str,
            files_filter: str = "",
            files_filter_text: Optional[Union[str, Sequence[str]]] = None
    ) -> None:
        self.json_tree = json.loads(json_tree)
        self.files_filter = files_filter

        self.files_filter_text = self._parse_files_filter_text(files_filter_text)

    @staticmethod
    def _parse_files_filter_text(files_filter_text: Optional[Union[str, Sequence[str]]]) -> List[str]:
        if not files_filter_text:
            return []

        if isinstance(files_filter_text, (list, tuple)):
            return [
                str(term).strip()
                for term in files_filter_text
                if str(term).strip()
            ]

        raw_text = str(files_filter_text).strip()

        if raw_text.startswith("["):
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, list):
                    return [
                        str(term).strip()
                        for term in parsed
                        if str(term).strip()
                    ]
            except json.JSONDecodeError:
                logger.warning("files_filter_text JSON inválido; aplicando fallback CSV")

        return [
            term.strip()
            for term in raw_text.split(",")
            if term.strip()
        ]

    @staticmethod
    def filter_files_by_name(
            json_tree: Dict[str, Any],
            files_filter: str,
            exclude_irrelevant: bool = True
    ) -> List[Dict[str, Any]]:
        filters = [f.strip() for f in files_filter.split(",") if f.strip()]
        matched_files = []

        def is_irrelevant_path(path: str) -> bool:
            if not exclude_irrelevant:
                return False

            irrelevant_patterns = [
                "__pycache__",
                ".pytest_cache",
                ".git",
                "node_modules",
                ".venv",
                "venv",
                ".idea",
                ".vscode",
                "*.pyc",
                "*.pyo",
                "*.pyd",
                ".DS_Store",
                "*.log",
                "*.tmp",
                ".env"
            ]

            path_lower = path.lower()
            for pattern in irrelevant_patterns:
                if pattern.startswith("*."):
                    if path_lower.endswith(pattern[1:]):
                        return True
                elif pattern in path_lower:
                    return True

            return False

        def traverse_tree(node: Dict[str, Any]) -> None:
            node_name = node.get("name", "")
            node_path = node.get("path", "")
            node_type = node.get("type", "")

            if is_irrelevant_path(node_path):
                return

            if node_type == "file":
                if not filters or any(fnmatch.fnmatch(node_name, pattern) for pattern in filters):
                    matched_files.append({
                        "name": node_name,
                        "path": node_path,
                        "type": node_type
                    })

            elif node_type == "directory":
                children = node.get("children", [])
                for child in children:
                    traverse_tree(child)

        traverse_tree(json_tree)

        return matched_files

    @staticmethod
    def filter_files_by_content(
            files: List[Dict[str, Any]],
            search_term: str,
            base_path: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        if not search_term or not search_term.strip():
            return files

        result = []
        base = base_path or Path.cwd()

        for file_info in files:
            file_path_str = file_info.get("path", "")

            if file_path_str.startswith("./"):
                file_path = base / file_path_str[2:]
            else:
                file_path = base / file_path_str

            try:
                if file_path.exists() and file_path.is_file():
                    content = FileServices.read_file(str(file_path)) or ""

                    if search_term in content:
                        result.append(file_info)
                        logger.info(f"Match encontrado em: {file_path.name}")
                else:
                    logger.warning(f"Arquivo não encontrado: {file_path}")
            except Exception as e:
                logger.warning(f"Erro ao ler {file_path}: {e}")

        return result

    def run(self, base_path: Optional[Path] = None) -> str:
        selected_files = self.filter_files_by_name(
            self.json_tree,
            self.files_filter
        )
        logger.info(f"Arquivos encontrados após filtro de nome: {len(selected_files)}")

        if self.files_filter_text:
            logger.info(f"Aplicando {len(self.files_filter_text)} filtro(s) de conteúdo...")

            for idx, search_term in enumerate(self.files_filter_text, 1):
                if not search_term or not search_term.strip():
                    continue

                display_term = search_term[:150] + "..." if len(search_term) > 150 else search_term
                logger.info(f"Filtro {idx}/{len(self.files_filter_text)}: '{display_term}'")

                selected_files = self.filter_files_by_content(
                    selected_files,
                    search_term,
                    base_path
                )

                logger.info(f"Arquivos restantes: {len(selected_files)}")

                if not selected_files:
                    logger.warning("Nenhum arquivo restante após filtro de conteúdo")
                    break

        logger.info(f"Total final de arquivos selecionados: {len(selected_files)}")
        return json.dumps(selected_files)
