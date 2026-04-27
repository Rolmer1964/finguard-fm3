import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text, _regex_owner_method

# ----------------------- Go -----------------------
class GoAnalyzer(BaseAnalyzer):
    language_name = 'go'

    def find_imported_identifiers(self, root, src: bytes):
        names = []
        def visit(n):
            if n.type == 'import_declaration':
                text = get_node_text(n, src)
                # import "fmt" | import m "math" | import ( "fmt" m "math" )
                for line in text.splitlines():
                    line = line.strip()
                    m = re.findall(r'(?:(\w+)\s+)?\"([^\"]+)\"', line)
                    for alias, path in m:
                        if alias:
                            names.append(alias)
                        else:
                            base = path.split('/')[-1]
                            names.append(base)
            for c in n.children:
                visit(c)
        visit(root)
        return list(dict.fromkeys(names))

    def find_type_nodes(self, root):
        # procurar struct e interface em type_declaration -> type_spec
        nodes = []
        def visit(n):
            if n.type == 'type_declaration':
                for ts in n.children:
                    if ts.type == 'type_spec':
                        for c in ts.children:
                            if c.type in ('struct_type', 'interface_type'):
                                nodes.append(ts)  # usaremos o type_spec para nome
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        # node é type_spec com filho struct_type|interface_type
        for c in node.children:
            if c.type == 'interface_type':
                return 'interface'
        return 'class'

    def get_type_name(self, node, src: bytes):
        # type_spec -> type_identifier
        for ch in node.children:
            if ch.type == 'type_identifier':
                return get_node_text(ch, src)
        return None

    def find_fields(self, type_node, src: bytes):
        # Ignorar (campos de struct não são variáveis de instância nomeadas em escopo de métodos)
        return {}

    def find_methods(self, type_node, src: bytes):
        # Métodos com receiver daquele type
        type_name = self.get_type_name(type_node, src)
        if not type_name:
            return []
        methods = []
        def visit(n):
            if n.type == 'method_declaration':
                # verificar receiver
                recv = n.child_by_field_name('receiver')
                ok = False
                if recv:
                    # procurar type_identifier dentro do receiver (suporta ponteiro)
                    tid = None
                    stack = [recv]
                    while stack:
                        x = stack.pop()
                        if x.type == 'type_identifier':
                            tid = get_node_text(x, src)
                            break
                        stack.extend(x.children)
                    if tid == type_name:
                        ok = True
                if ok:
                    # nome do método
                    for s in n.children:
                        if s.type == 'identifier':
                            methods.append(get_node_text(s, src))
                            break
            for c in n.children:
                visit(c)
        # métodos estão no nível do arquivo
        root = type_node
        while root.parent is not None:
            root = root.parent
        visit(root)
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None and fn.type == 'selector_expression':
                obj = fn.child_by_field_name('operand')
                field = fn.child_by_field_name('field')
                if obj is not None and field is not None:
                    return get_node_text(obj, src), get_node_text(field, src)
            elif fn is not None and fn.type == 'identifier':
                return None, get_node_text(fn, src)
        text = get_node_text(node, src)
        return _regex_owner_method(text)
