import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text
from pathlib import Path
from typing import List, Optional, Dict, List

# ----------------------- Python -----------------------
class PythonAnalyzer(BaseAnalyzer):
    language_name = 'python'

    def __init__(self, current_file: Optional[str] = None):
        self.current_file = current_file

    def find_imported_identifiers(self, root, src: bytes) -> Dict[str, str]:
        """
        Retorna um mapeamento: nome_usado_no_codigo -> nome_do_arquivo_owner (último segmento do módulo).
        Exemplos:
          - import json                => {'json': 'json'}
          - import a.b as c            => {'c': 'b'}
          - from x.y.m import foo      => {'foo': 'm'}
          - from src.pkg.mod import A  => {'A': 'mod'}
        """
        imported: Dict[str, str] = {}

        def add(name: str, module_full: Optional[str]):
            if not name:
                return
            owner = (module_full or name).split('.')[-1]
            imported[name] = owner

        for ch in root.children:
            if ch.type == 'import_statement':
                text = get_node_text(ch, src).strip()
                # "import os, sys as s"
                body = text[len('import'):].strip()
                for part in body.split(','):
                    token = part.strip()
                    if not token:
                        continue
                    if ' as ' in token:
                        left, alias = token.split(' as ', 1)
                        add(alias.strip(), left.strip())
                    else:
                        # import a.b.c -> nome visível: c
                        mod_full = token
                        vis_name = mod_full.split('.')[-1].strip()
                        add(vis_name, mod_full.strip())

            elif ch.type == 'import_from_statement':
                text = get_node_text(ch, src).strip()
                # "from a.b.c import X as Y, Z"
                m = re.match(r'^from\s+([^\s]+)\s+import\s+(.+)$', text)
                if not m:
                    continue
                module_full = m.group(1).strip()
                items = m.group(2).strip()
                # remove parênteses opcionais
                if items.startswith('(') and items.endswith(')'):
                    items = items[1:-1]
                for item in items.split(','):
                    token = item.strip()
                    if not token or token == '*':
                        continue
                    if ' as ' in token:
                        left, alias = token.split(' as ', 1)
                        add(alias.strip(), module_full)
                    else:
                        add(token, module_full)

        return imported

    def find_type_nodes(self, root) -> List:
        nodes = []
        def visit(n):
            if n.type == 'class_definition':
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'class'

    def get_type_name(self, node, src: bytes) -> Optional[str]:
        for ch in node.children:
            if ch.type == 'identifier':
                return get_node_text(ch, src)
        name_node = node.child_by_field_name('name')
        if name_node is not None:
            return get_node_text(name_node, src)
        return None

    def find_fields(self, type_node, src: bytes) -> Dict[str, Optional[str]]:
        # Campos de classe declarados no corpo (atributos de classe).
        fields: Dict[str, Optional[str]] = {}
        for c in type_node.children:
            if c.type == 'block':
                for st in c.children:
                    if st.type == 'expression_statement' and st.children:
                        expr = st.children[0]
                        if expr.type == 'assignment' and expr.children:
                            left = expr.children[0]
                            if left.type == 'identifier':
                                name = get_node_text(left, src)
                                fields[name] = None
        return fields

    def find_methods(self, type_node, src: bytes) -> List[str]:
        methods: List[str] = []
        for ch in type_node.children:
            if ch.type == 'block':
                for item in ch.children:
                    if item.type == 'function_definition':
                        nm = item.child_by_field_name('name')
                        if nm is not None:
                            methods.append(get_node_text(nm, src))
                        else:
                            for s in item.children:
                                if s.type == 'identifier':
                                    methods.append(get_node_text(s, src))
                                    break
                    elif item.type == 'decorated_definition':
                        inner = item.child_by_field_name('definition')
                        if inner is not None and inner.type == 'function_definition':
                            nm = inner.child_by_field_name('name')
                            if nm is not None:
                                methods.append(get_node_text(nm, src))
                            else:
                                for s in inner.children:
                                    if s.type == 'identifier':
                                        methods.append(get_node_text(s, src))
                                        break
        return methods

    def find_module_functions(self, root, src: bytes) -> List[str]:
        funcs: List[str] = []
        for ch in root.children:
            if ch.type == 'function_definition':
                nm = ch.child_by_field_name('name')
                if nm is not None:
                    funcs.append(get_node_text(nm, src))
                else:
                    for s in ch.children:
                        if s.type == 'identifier':
                            funcs.append(get_node_text(s, src))
                            break
            elif ch.type == 'decorated_definition':
                inner = ch.child_by_field_name('definition')
                if inner is not None and inner.type == 'function_definition':
                    nm = inner.child_by_field_name('name')
                    if nm is not None:
                        funcs.append(get_node_text(nm, src))
                    else:
                        for s in inner.children:
                            if s.type == 'identifier':
                                funcs.append(get_node_text(s, src))
                                break
        return funcs

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if node.type == 'call':
            fn = node.child_by_field_name('function')
            if fn is not None:
                if fn.type == 'attribute':
                    obj = fn.child_by_field_name('object')
                    attr = fn.child_by_field_name('attribute')
                    if obj is not None and attr is not None:
                        return get_node_text(obj, src), get_node_text(attr, src)
                elif fn.type == 'identifier':
                    return None, get_node_text(fn, src)
                else:
                    return None, get_node_text(fn, src)
        return None, None

    def find_method_invocations(
        self,
        anchor_node,
        src: bytes,
        fields: Dict[str, Optional[str]],
        imported_map: Dict[str, str],
        methods: Optional[List[str]] = None,
        invocations: Optional[List[Dict]] = None,
        cur_class_name: Optional[str] = None
    ) -> List[Dict]:
        if invocations is None:
            invocations = []
        seen = set()

        def visit(n):
            if n.type == 'call':
                key = (n.start_byte, n.end_byte)
                if key in seen:
                    for c in n.children:
                        visit(c)
                    return
                seen.add(key)

                owner, method = self.extract_owner_and_method_from_call(n, src)
                # Ignora dunder (ex.: __str__, __repr__)
                if method and re.match(r'^__\w+__$', method):
                    for c in n.children:
                        visit(c)
                    return

                record_owner = owner if owner is not None else None
                owner_type = 'unknown'
                owner_class = None

                # Normaliza ex.: "uuid4()" -> "uuid4"
                if record_owner:
                    record_owner = re.sub(r'\(\)$', '', record_owner)

                if record_owner in ('self', 'this', 'cls') and cur_class_name and methods and method in methods:
                    # chamada a método da própria classe/arquivo
                    record_owner = 'this'
                    owner_type = 'class' if record_owner == 'cls' else 'instance'
                    owner_class = cur_class_name
                elif record_owner:
                    owner_head = record_owner.split('.')[0]
                    if owner_head in imported_map:
                        # owner é um identificador importado (módulo/classe)
                        owner_type = 'class'
                        owner_class = imported_map[owner_head]
                        record_owner = owner_head
                    elif owner_head in ('self', 'this'):
                        owner_type = 'instance'
                else:
                    # chamada identificador simples: checar imports (from X import foo)
                    if method in imported_map:
                        record_owner = imported_map[method]
                        owner_type = 'class'
                        owner_class = imported_map[method]
                    # chamada a função local do mesmo arquivo
                    elif methods and method in methods and cur_class_name:
                        record_owner = 'this'
                        owner_type = 'class'
                        owner_class = cur_class_name

                if method:
                    invocations.append({
                        "owner": record_owner,
                        "owner_type": owner_type,
                        "owner_class": owner_class,
                        "method": method
                    })

                for c in n.children:
                    visit(c)
            else:
                for c in n.children:
                    visit(c)

        visit(anchor_node)
        return invocations

    def extract(self, root, src: bytes) -> Dict:
        imported_map = self.find_imported_identifiers(root, src)
        imported_names = list(imported_map.keys())
        class_nodes = self.find_type_nodes(root)

        if class_nodes:
            # Se houver classes, analisa cada uma; aqui retornamos a última encontrada (como no código anterior)
            info = None
            for cn in class_nodes:
                class_name = self.get_type_name(cn, src)
                fields = self.find_fields(cn, src)
                methods = self.find_methods(cn, src)
                invocations = self.find_method_invocations(
                    cn, src, fields, imported_map, methods=methods, cur_class_name=class_name
                )
                info = {
                    "classe": class_name,
                    "interface": None,
                    "classes_importadas": imported_names,
                    "metodos": methods,
                    "metodos_externos": invocations
                }
            return info

        # Sem classes: tratar como "módulo" e usar nome do arquivo como classe
        methods = self.find_module_functions(root, src)
        file_stem = None
        try:
            if getattr(self, 'current_file', None):
                file_stem = Path(self.current_file).stem
        except Exception:
            pass
        if not file_stem:
            file_stem = "__module__"

        invocations = self.find_method_invocations(
            root, src, {}, imported_map, methods=methods, cur_class_name=file_stem
        )

        return {
            "classe": file_stem,
            "interface": None,
            "classes_importadas": imported_names,
            "metodos": methods,
            "metodos_externos": invocations
        }
