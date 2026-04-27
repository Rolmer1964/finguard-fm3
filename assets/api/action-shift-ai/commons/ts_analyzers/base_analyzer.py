import re

def get_node_text(node, source_code: bytes) -> str:
    return source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

def _regex_owner_method(text: str):
    # Fallback genérico: captura owner.method( ou owner::method(
    m = re.search(r'([A-Za-z_][\w]*)\s*(?:\.|::)\s*([A-Za-z_][\w]*)\s*\(', text)
    if m:
        return m.group(1), m.group(2)
    return None, None

class BaseAnalyzer:
    """
    Classe base para padronizar extração.
    Métodos a sobrescrever conforme a linguagem.
    """
    language_name = "base"

    def find_imported_identifiers(self, root, src: bytes):
        return []

    def find_type_nodes(self, root):
        return []

    def get_type_kind(self, node) -> str:
        # "class" | "interface" | outros mapeados a um dos dois acima
        return "class"

    def get_type_name(self, node, src: bytes) -> str | None:
        # Por padrão tenta primeiro filho identifier
        for ch in node.children:
            if ch.type == 'identifier':
                return get_node_text(ch, src)
        return None

    def find_fields(self, type_node, src: bytes) -> dict:
        # Retorna {nome_campo: tipo_ou_None}
        return {}

    def find_methods(self, type_node, src: bytes) -> list:
        return []

    def extract_owner_and_method_from_call(self, node, src: bytes):
        return None, None

    def find_method_invocations(self, anchor_node, src: bytes, fields: dict,
                                imported: list, methods: list, inv: None | list = None):
        if inv is None:
            inv = []
        # Padrão: detectar nós de chamada via nomes comuns; subclasses podem sobrescrever
        call_types = {'call_expression', 'function_call_expression', 'invocation_expression', 'call'}
        stack = [anchor_node]
        while stack:
            n = stack.pop()
            if n.type in call_types or 'call_expression' in n.type or 'invocation' in n.type:
                owner, method = self.extract_owner_and_method_from_call(n, src)
                if owner and method:
                    owner_norm = owner.strip()
                    fields_norm = {k.strip(): v for k, v in fields.items()}
                    if owner_norm in fields_norm:
                        inv.append({
                            "owner": owner,
                            "owner_type": "instance",
                            "owner_class": fields_norm[owner_norm],
                            "method": method
                        })
                    elif owner_norm in imported:
                        inv.append({
                            "owner": owner,
                            "owner_type": "class",
                            "owner_class": owner,
                            "method": method
                        })
                    else:
                        inv.append({
                            "owner": owner,
                            "owner_type": "unknown",
                            "owner_class": None,
                            "method": method
                        })
            stack.extend(n.children)
        return inv

    def extract(self, root, src: bytes):
        imported = self.find_imported_identifiers(root, src)
        type_nodes = self.find_type_nodes(root)
        result = None
        for tnode in type_nodes:
            kind = self.get_type_kind(tnode)
            name = self.get_type_name(tnode, src)
            fields = self.find_fields(tnode, src)
            methods = self.find_methods(tnode, src)
            invocations = self.find_method_invocations(tnode, src, fields, imported, methods)
            result = {
                "classe": name if kind == 'class' else None,
                "interface": name if kind == 'interface' else None,
                "classes_importadas": imported,
                "metodos": methods,
                "metodos_externos": invocations
            }
        return result
