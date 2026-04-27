import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text, _regex_owner_method

# ----------------------- Swift -----------------------
class SwiftAnalyzer(BaseAnalyzer):
    language_name = 'swift'

    def find_imported_identifiers(self, root, src: bytes):
        names = []
        def visit(n):
            if n.type == 'import_declaration':
                text = get_node_text(n, src)
                m = re.search(r'\bimport\s+([A-Za-z_]\w*)', text)
                if m:
                    names.append(m.group(1))
            for c in n.children:
                visit(c)
        visit(root)
        return names

    def find_type_nodes(self, root):
        nodes = []
        def visit(n):
            if n.type in ('class_declaration', 'protocol_declaration', 'struct_declaration'):
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'interface' if node.type == 'protocol_declaration' else 'class'

    def get_type_name(self, node, src: bytes):
        # procurar identifier após 'class'/'struct'/'protocol'
        for ch in node.children:
            if ch.type in ('identifier', 'type_identifier'):
                return get_node_text(ch, src)
        return None

    def find_fields(self, type_node, src: bytes):
        fields = {}
        def visit(n):
            if n.type == 'variable_declaration':
                # pegar primeiro identifier (pattern)
                name = None
                for s in n.children:
                    if s.type in ('identifier', 'simple_identifier'):
                        name = get_node_text(s, src)
                        break
                if name:
                    fields[name] = None
            for c in n.children:
                visit(c)
        visit(type_node)
        return fields

    def find_methods(self, type_node, src: bytes):
        methods = []
        def visit(n):
            if n.type == 'function_declaration':
                for s in n.children:
                    if s.type in ('identifier', 'simple_identifier'):
                        methods.append(get_node_text(s, src))
                        break
            for c in n.children:
                visit(c)
        visit(type_node)
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if node.type == 'function_call_expression':
            called = node.child_by_field_name('called_expression')
            if called is not None:
                # member_access_expression -> base . name
                if called.type == 'member_access_expression':
                    base = called.child_by_field_name('base')
                    name = called.child_by_field_name('name')
                    if base is not None and name is not None:
                        return get_node_text(base, src), get_node_text(name, src)
                elif called.type in ('identifier', 'simple_identifier'):
                    return None, get_node_text(called, src)
        text = get_node_text(node, src)
        return _regex_owner_method(text)
