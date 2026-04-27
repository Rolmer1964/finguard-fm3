import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text, _regex_owner_method

# ----------------------- Java -----------------------
class JavaAnalyzer(BaseAnalyzer):
    language_name = 'java'

    def find_imported_identifiers(self, root, src: bytes):
        imported = []
        for child in root.children:
            if child.type == 'import_declaration':
                text = get_node_text(child, src)
                m = re.search(r'import\s+([\w\.]+)\s*;', text)
                if m:
                    imported.append(m.group(1).split('.')[-1])
        return imported

    def find_type_nodes(self, root):
        nodes = []
        def visit(n):
            if n.type in ('class_declaration', 'interface_declaration'):
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'class' if node.type == 'class_declaration' else 'interface'

    def find_fields(self, class_node, src: bytes) -> dict:
        fields = {}
        for child in class_node.children:
            if child.type == 'class_body':
                for member in child.children:
                    if member.type == 'field_declaration':
                        type_name = None
                        var_name = None
                        for sub in member.children:
                            if sub.type == 'type_identifier':
                                type_name = get_node_text(sub, src)
                            if sub.type == 'variable_declarator':
                                for v in sub.children:
                                    if v.type == 'identifier':
                                        var_name = get_node_text(v, src)
                        if type_name and var_name:
                            fields[var_name] = type_name
        return fields

    def find_methods(self, class_node, src: bytes) -> list:
        methods = []
        for child in class_node.children:
            if child.type == 'class_body':
                for member in child.children:
                    if member.type == 'method_declaration':
                        for sub in member.children:
                            if sub.type == 'identifier':
                                methods.append(get_node_text(sub, src))
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        # Java: method_invocation
        if node.type == 'method_invocation':
            children = list(node.children)
            owner = None
            method = None
            if len(children) >= 2:
                if children[0].type in ('field_access', 'identifier'):
                    owner = get_node_text(children[0], src)
                for c in children:
                    if c.type == 'identifier':
                        method = get_node_text(c, src)
            return owner, method
        # fallback para outras variações
        text = get_node_text(node, src)
        return _regex_owner_method(text)

    def find_method_invocations(self, anchor_node, src: bytes, fields: dict,
                                imported: list, methods: list, inv=None):
        # Para Java seguimos o comportamento original visitando method_invocation
        if inv is None:
            inv = []
        def visit(n):
            if n.type == 'method_invocation':
                owner, method = self.extract_owner_and_method_from_call(n, src)
                if owner and method:
                    owner_norm = owner.strip()
                    fields_norm = {k.strip(): v for k, v in fields.items()}
                    if owner_norm in fields_norm:
                        inv.append({"owner": owner, "owner_type": "instance", "owner_class": fields_norm[owner_norm], "method": method})
                    elif any(owner_norm == ic for ic in imported):
                        inv.append({"owner": owner, "owner_type": "class", "owner_class": owner, "method": method})
                    else:
                        inv.append({"owner": owner, "owner_type": "unknown", "owner_class": None, "method": method})
            for c in n.children:
                visit(c)
        visit(anchor_node)
        return inv
