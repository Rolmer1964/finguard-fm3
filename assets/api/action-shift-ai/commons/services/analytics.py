import json
import re
import os
import fnmatch

from pathlib import Path
from logging import getLogger
from collections import OrderedDict

from typing import Any, Iterable, Optional, Dict, List, Set, Pattern, Sequence

from commons.ts_analyzers.maps import TreeSitterAnalyserMaps

logger = getLogger()

DEFAULT_IGNORES_FOLDERS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".DS_Store",
}

filters = {
    "ignore_dirs": ["test", "tests", "__tests__", "testing", "spec", "node_modules", "vendor", "dist", "build", "out"],
    "ignore_extensions": [".json", ".lock", ".xml", ".yml", ".yaml", ".md", ".txt"],
    "ignore_patterns": [".min."],
    "max_file_size_mb": 2
}


class FileAnalyticsServices:
    def __init__(self):
        self.ts_analytics_maps = TreeSitterAnalyserMaps()

    def is_irrelevant_file(self, file_path: Path) -> bool:
        if file_path.name.startswith("."):
            return True
        if any(part in filters["ignore_dirs"] for part in file_path.parts):
            return True
        if file_path.suffix in filters["ignore_extensions"]:
            return True
        if any(pattern in file_path.name for pattern in filters["ignore_patterns"]):
            return True
        try:
            if file_path.stat().st_size > filters["max_file_size_mb"] * 1024 * 1024:
                return True
        except Exception:
            return True
        return False

    def analyze_file(self, file_path: Path):
        ext = file_path.suffix
        parser = self.ts_analytics_maps.get_parser(ext)

        code_text = file_path.read_text(encoding='utf-8', errors='ignore')
        num_lines = len(code_text.splitlines())

        code_bytes = code_text.encode('utf-8', errors='ignore')
        tree = parser.parse(code_bytes)

        analyzer = self.ts_analytics_maps.get_analyser(ext)
        try:
            analyzer.current_file = str(file_path)
        except Exception as e:
            logger.error(f"A problem happen analysing file: {file_path}: {e}")
            pass
        info = analyzer.extract(tree.root_node, code_bytes)
        return [info, num_lines]

    def analyze_directory(self, directory: str) -> dict:
        project_root = Path(directory).resolve()
        data = dict()
        total_files = 0
        total_lines = 0
        for path in project_root.rglob("*"):
            if path.is_file() and not self.is_irrelevant_file(path):
                file_analytics, lines_count = self.analyze_file(path)
                if file_analytics is not None:
                    total_files += 1
                    total_lines += lines_count
                    data["total_arquivos"] = total_files
                    data["total_linhas_analisadas"] = total_lines
                    data["mapa"].append(file_analytics)
        return data

    def create_md_from_analyze_output(
            self,
            data: Dict[str, Any] | List[Dict[str, Any]],
            include_unknown_owner: bool = False,
            include_self_owner: bool = False,
            ignore_owner_classes: Optional[Set[str]] = None,
            ignore_method_names: Optional[Set[str]] = None,
            ignore_owner_regex: Optional[List[str]] = None,
            ignore_method_regex: Optional[List[str]] = None,
            use_default_ignores: bool = True,
    ) -> str:
        mapa: Iterable[Dict[str, Any]] = data.get("mapa") if isinstance(data, dict) else data
        if mapa is None:
            raise ValueError("Entrada inválida: espere um dict com chave 'mapa' ou uma lista de itens.")

        # Defaults de ignorados
        default_ignore_owner_classes = {
            # Tipos utilitários mais poluentes
            "optional", "list", "map", "collectors", "collections", "arrays", "objects",
            "uuid", "bigdecimal", "localdate", "localdatetime", "date", "zoneid",
            "responseentity", "httpstatus", "ioutils", "string",
        }
        default_ignore_method_names = {
            # Builders/factories/comuns
            "builder", "build", "of", "ofnullable", "empty",
            "frombean", "fromstring", "valueof", "now", "create",
            "tostring", "entry", "ofpattern",
        }
        default_ignore_owner_regex: List[str] = [
            # Ex.: ignorar qualquer coisa terminando com "Builder" (opcional)
            r".*Builder$",
        ]
        default_ignore_method_regex: List[str] = [
            # Adicione aqui padrões adicionais se necessário
        ]

        # Merge de ignores (case-insensitive para names; regex compila como informado)
        owners_ign_lower = set()
        methods_ign_lower = set()
        owners_regex: List[Pattern[str]] = []
        methods_regex: List[Pattern[str]] = []

        if use_default_ignores:
            owners_ign_lower |= default_ignore_owner_classes
            methods_ign_lower |= default_ignore_method_names
            owners_regex += [re.compile(p) for p in default_ignore_owner_regex]
            methods_regex += [re.compile(p) for p in default_ignore_method_regex]

        if ignore_owner_classes:
            owners_ign_lower |= {o.lower() for o in ignore_owner_classes}
        if ignore_method_names:
            methods_ign_lower |= {m.lower() for m in ignore_method_names}
        if ignore_owner_regex:
            owners_regex += [re.compile(p) for p in ignore_owner_regex]
        if ignore_method_regex:
            methods_regex += [re.compile(p) for p in ignore_method_regex]

        def should_skip(call: Dict[str, Any], current_class: str) -> bool:
            oc = call.get("owner_class")
            method = call.get("method")
            if not method:
                return True

            # Unknown owners
            if not oc or oc == "":
                return not include_unknown_owner

            oc_norm = str(oc)
            m_norm = str(method)
            oc_lower = oc_norm.lower()
            m_lower = m_norm.lower()

            # Ignora self
            if not include_self_owner and oc_norm == current_class:
                return True

            # Ignora por listas
            if oc_lower in owners_ign_lower:
                return True
            if m_lower in methods_ign_lower:
                return True

            # Ignora por regex
            for rx in owners_regex:
                if rx.match(oc_norm):
                    return True
            for rx in methods_regex:
                if rx.match(m_norm):
                    return True

            return False

        def group_by_owner_class(
                calls: List[Dict[str, Any]],
                current_class: str,
        ) -> OrderedDict[str, OrderedDict[str, None]]:
            groups: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
            for call in calls or []:
                if should_skip(call, current_class):
                    continue

                oc = call.get("owner_class")
                method = call.get("method")
                if not oc or not method:
                    continue

                if oc not in groups:
                    groups[oc] = OrderedDict()
                groups[oc].setdefault(method, None)  # dedup preservando ordem
            return groups

        lines: List[str] = []
        for item in mapa:
            classe = item.get("classe")
            if classe:
                lines.append(f"{classe}:")
            grouped = group_by_owner_class(item.get("metodos_externos", []), classe)
            for owner_class, methods_map in grouped.items():
                lines.append(f"     -{owner_class}:")
                for method in methods_map.keys():
                    lines.append(f"         -{method}")

        md = "\n".join(lines) + "\n"
        return md

    def generate_markdown_tree(
        self,
        path: str = ".",
        ignore_patterns: Iterable[str] = (),
        max_depth: int | None = None,
        include_hidden: bool = False,
    ) -> str:
        repo = Path(path).resolve()
        patterns = list(DEFAULT_IGNORES_FOLDERS) + list(ignore_patterns)

        root_label = f"{repo.name or repo.as_posix().rstrip('/')}/"
        lines = [root_label]
        lines.extend(
            self.build_tree_lines(
                str(repo),
                prefix="",
                depth=1,
                max_depth=max_depth,
                ignore_patterns=patterns,
                include_hidden=include_hidden,
            )
        )

        md = [*lines]
        result = "\n".join(md)

        print(f"MD Tree: \n\n{result}")
        return result

    def should_skip(self, name: str, ignore_patterns: Sequence[str], include_hidden: bool) -> bool:
        if not include_hidden and name.startswith("."):
            return True
        return any(fnmatch.fnmatch(name, pat) for pat in ignore_patterns)

    def iter_entries(
        self,
        dir_path: str,
        ignore_patterns: Sequence[str],
        include_hidden: bool,
    ) -> List[os.DirEntry]:
        with os.scandir(dir_path) as it:
            entries = [
                e
                for e in it
                if not self.should_skip(e.name, ignore_patterns, include_hidden)
            ]
        entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        return entries

    def build_tree_lines(
        self,
        root: str,
        prefix: str,
        depth: int,
        max_depth: int | None,
        ignore_patterns: Sequence[str],
        include_hidden: bool,
    ) -> List[str]:
        if max_depth is not None and depth > max_depth:
            return []

        lines: List[str] = []
        entries = self.iter_entries(root, ignore_patterns, include_hidden)
        for i, entry in enumerate(entries):
            is_last = i == (len(entries) - 1)
            connector = "└── " if is_last else "├── "
            if entry.is_dir(follow_symlinks=False):
                lines.append(f"{prefix}{connector}📂 {entry.name}/")
                extension = "    " if is_last else "│   "
                # Avança apenas se não ultrapassar a profundidade
                if max_depth is None or depth < max_depth:
                    lines.extend(
                        self.build_tree_lines(
                            entry.path,
                            prefix + extension,
                            depth + 1,
                            max_depth,
                            ignore_patterns,
                            include_hidden,
                        )
                    )
            else:
                lines.append(f"{prefix}{connector}📝 {entry.name}")
        return lines

    def generate_json_tree(
        self,
        path: str = ".",
        ignore_patterns: Iterable[str] = (),
        max_depth: int | None = None,
        include_hidden: bool = False,
    ) -> str:
        repo = Path(path).resolve()

        # Combina padrões de ignorar padrão com os fornecidos
        patterns = list(DEFAULT_IGNORES_FOLDERS) + list(ignore_patterns)

        def should_ignore(name: str) -> bool:
            """Verifica se o arquivo/pasta deve ser ignorado baseados nos padrões."""
            if not include_hidden and name.startswith(".") and name != ".":
                return True
            for pattern in patterns:
                if fnmatch.fnmatch(name, pattern):
                    return True
            return False

        def build_node(current_path: Path, current_depth: int) -> Dict[str, Any]:
            """Constrói recursivamente o nó do dicionário para o JSON."""
            node: Dict[str, Any] = {
                "name": current_path.name or current_path.as_posix().rstrip('/'),
                "path": str(current_path),
                "type": "directory" if current_path.is_dir() else "file"
            }

            # Lógica de parada por profundidade
            if max_depth is not None and current_depth > max_depth:
                return node

            if current_path.is_dir():
                children = []
                try:
                    # [Nota] iterdir() não garante ordem, sorted() ajuda na consistência
                    for item in sorted(current_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                        if not should_ignore(item.name):
                            children.append(build_node(item, current_depth + 1))
                except PermissionError:
                    node["error"] = "Permission Denied"

                node["children"] = children

            return node

        # Inicia a construção da árvore a partir da raiz (profundidade 0)
        tree_data = build_node(repo, 0)

        # Retorna o dicionário convertido para string JSON com indentação
        result = json.dumps(tree_data, indent=2, ensure_ascii=False)
        print(f"Json Tree: \n\n{result}")
        return result
