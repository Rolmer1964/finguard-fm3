import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text

# ----------------------- Kotlin -----------------------
class KotlinAnalyzer(BaseAnalyzer):
    language_name = 'kotlin'

    def find_imported_identifiers(self, root, src: bytes):
        text = src.decode('utf-8', 'ignore')
        names = []

        # 1) Varredura robusta por regex (independe da árvore)
        pat = re.compile(
            r'^\s*import\s+([^\s;]+?)(?:\s+as\s+([A-Za-z_]\w*))?\s*;?\s*(?://.*)?$',
            re.MULTILINE
        )
        for full, alias in pat.findall(text):
            if alias:
                names.append(alias.strip('`'))
            else:
                last = full.split('.')[-1]
                if last == '*':
                    continue
                names.append(last.strip('`'))

        # 2) Complemento via AST (caso necessário)
        if not names:
            stack = [root]
            while stack:
                n = stack.pop()
                if n.type in ('import_header', 'import_declaration', 'import_directive', 'import_statement'):
                    line = get_node_text(n, src)
                    m = re.search(r'import\s+([^\s;]+?)(?:\s+as\s+([A-Za-z_]\w*))?', line)
                    if m:
                        full, alias = m.group(1), m.group(2)
                        if alias:
                            names.append(alias.strip('`'))
                        else:
                            last = full.split('.')[-1]
                            if last != '*':
                                names.append(last.strip('`'))
                stack.extend(n.children)

        # Deduplica preservando a ordem
        out, seen = [], set()
        for name in names:
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def find_type_nodes(self, root):
        nodes = []
        def visit(n):
            if n.type in ('class_declaration', 'interface_declaration', 'object_declaration'):
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'interface' if node.type == 'interface_declaration' else 'class'

    def get_type_name(self, node, src: bytes):
        for ch in node.children:
            if ch.type in ('type_identifier', 'simple_identifier', 'identifier'):
                return get_node_text(ch, src)
        return None

    # Helpers
    def _strip_generics(self, s: str) -> str:
        out, depth = [], 0
        for ch in s:
            if ch == '<':
                depth += 1
            elif ch == '>':
                if depth > 0:
                    depth -= 1
            elif depth == 0:
                out.append(ch)
        return ''.join(out)

    def _split_owner_method_from_callee(self, callee: str):
        callee = callee.strip().replace('`', '')
        callee = self._strip_generics(callee).replace('?.', '.').replace('!!', '')
        if not callee:
            return None, None
        if '.' not in callee:
            return None, callee.split('<', 1)[0].strip()
        owner, method = callee.rsplit('.', 1)
        method = method.split('<', 1)[0].strip()
        owner_id = re.split(r'\.|::', owner)[-1].strip().replace('!!', '').replace('?', '')
        if not owner_id or not method:
            return None, None
        return owner_id, method

    def _find_type_root(self, node):
        # procura nó de tipo dentro do parâmetro/propriedade
        targets = ('type', 'type_reference', 'user_type', 'simple_user_type')
        stack = [node]
        while stack:
            x = stack.pop()
            if x.type in targets:
                return x
            stack.extend(x.children)
        return None

    def _base_type_identifier_from(self, type_root, src: bytes):
        # retorna o identificador base do tipo (ex.: List<...> -> List, pkg.Foo -> Foo)
        base = None
        def visit(y):
            nonlocal base
            if base is not None:
                return
            if y.type in ('type_identifier', 'simple_identifier'):
                tok = get_node_text(y, src)
                if tok not in ('*', '_'):
                    base = tok
                return
            for ch in y.children:
                visit(ch)
        visit(type_root)
        return base

    def _extract_type_from_node(self, node, src: bytes):
        type_root = self._find_type_root(node)
        if type_root:
            base = self._base_type_identifier_from(type_root, src)
            if base:
                return base
        # Fallback regex (ex.: ": CreditOrchestration")
        txt = get_node_text(node, src)
        m = re.search(r':\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)', txt)
        if m:
            return m.group(1).split('.')[-1]
        return None

    def find_fields(self, type_node, src: bytes) -> dict:
        fields = {}

        # 1) Campos via parâmetros do construtor primário (val/var)
        def visit_ctor(n):
            if n.type == 'class_parameter':
                txt = get_node_text(n, src)
                if re.search(r'\b(val|var)\b', txt):
                    name = None
                    for ch in n.children:
                        if ch.type in ('simple_identifier', 'identifier'):
                            name = get_node_text(ch, src)
                            break
                    typ = self._extract_type_from_node(n, src)
                    if name:
                        fields[name] = typ
            for c in n.children:
                visit_ctor(c)
        visit_ctor(type_node)

        # 2) Propriedades no corpo da classe
        def visit_props(n):
            if n.type == 'property_declaration':
                # nome
                name = None
                var_decl = None
                for ch in n.children:
                    if ch.type == 'variable_declaration':
                        var_decl = ch
                        break
                if var_decl:
                    for s in var_decl.children:
                        if s.type in ('simple_identifier', 'identifier'):
                            name = get_node_text(s, src)
                            break
                # tipo
                typ = self._extract_type_from_node(n, src)
                if name:
                    fields[name] = typ
            for c in n.children:
                visit_props(c)
        visit_props(type_node)

        return fields

    def find_methods(self, type_node, src: bytes) -> list:
        methods = []
        def visit(n):
            if n.type == 'function_declaration':
                for s in n.children:
                    if s.type in ('simple_identifier', 'identifier'):
                        methods.append(get_node_text(s, src))
                        break
            for c in n.children:
                visit(c)
        visit(type_node)
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if 'call_expression' in node.type:
            text = get_node_text(node, src)
            idx = text.find('(')
            if idx == -1:
                return None, None
            callee = text[:idx]
            return self._split_owner_method_from_callee(callee)
        return None, None

    def find_method_invocations(self, anchor_node, src: bytes, fields: dict, imported: list, methods: list, inv=None):
        if inv is None:
            inv = []
        seen = set()
        stack = [anchor_node]
        fields_norm = {k.strip(): v for k, v in (fields or {}).items()}

        while stack:
            n = stack.pop()
            if n.type == 'call_expression':
                key = (n.start_byte, n.end_byte)
                if key in seen:
                    stack.extend(n.children)
                    continue
                seen.add(key)

                owner, method = self.extract_owner_and_method_from_call(n, src)
                if owner and method:
                    if owner in fields_norm:
                        inv.append({
                            "owner": owner,
                            "owner_type": "instance",
                            "owner_class": fields_norm[owner],
                            "method": method
                        })
                    elif owner in imported:
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
