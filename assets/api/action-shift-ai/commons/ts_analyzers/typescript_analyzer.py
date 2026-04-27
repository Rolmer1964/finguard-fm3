import re
from commons.ts_analyzers.base_analyzer import get_node_text, _regex_owner_method
from commons.ts_analyzers.javascript_analyzer import JavaScriptAnalyzer


# ----------------------- TypeScript / TSX -----------------------
class TypeScriptAnalyzer(JavaScriptAnalyzer):
    language_name = 'typescript'

    def find_imported_identifiers(self, root, src: bytes):
        names, seen = [], set()

        def add(n: str | None):
            if n and n not in seen:
                seen.add(n)
                names.append(n)

        stack = [root]
        while stack:
            n = stack.pop()
            if n.type in ('import_statement', 'import_declaration'):
                txt = get_node_text(n, src)
                m = re.search(r'^\s*import\s+(.+?)\s+from\s+[\'"][^\'"]+[\'"]\s*;?', txt, re.S)
                if m:
                    left = m.group(1).strip()
                    # import type ...
                    left = re.sub(r'^\s*type\s+', '', left)
                    if left.startswith('{'):
                        inside = re.search(r'\{(.*)\}', left, re.S)
                        if inside:
                            for tok in inside.group(1).split(','):
                                tok = tok.strip()
                                if not tok:
                                    continue
                                tok = re.sub(r'^\s*type\s+', '', tok)
                                if ' as ' in tok:
                                    add(tok.split(' as ', 1)[1].strip())
                                else:
                                    add(tok)
                    elif left.startswith('*'):
                        m2 = re.search(r'\*\s+as\s+([A-Za-z_$][\w$]*)', left)
                        if m2:
                            add(m2.group(1))
                    else:
                        parts = [p.strip() for p in left.split(',')]
                        if parts and parts[0]:
                            add(parts[0])
                        if len(parts) > 1 and parts[1].startswith('{'):
                            inside = re.search(r'\{(.*)\}', parts[1], re.S)
                            if inside:
                                for tok in inside.group(1).split(','):
                                    tok = tok.strip()
                                    tok = re.sub(r'^\s*type\s+', '', tok)
                                    if ' as ' in tok:
                                        add(tok.split(' as ', 1)[1].strip())
                                    else:
                                        add(tok)
                # import 'module'; -> ignora
            stack.extend(n.children)
        return names

    # ---------------- Helpers ----------------
    def _base_type_from_annotation_text(self, text: str) -> str | None:
        if not text:
            return None
        t = text.lstrip(':').strip()
        if not t:
            return None
        t = t.split('|', 1)[0].split('&', 1)[0].strip()
        if '<' in t:
            t = t.split('<', 1)[0].strip()
        while t.endswith('[]'):
            t = t[:-2].strip()
        if '.' in t:
            t = t.rsplit('.', 1)[1].strip()
        t = re.sub(r'^(public|private|protected|readonly)\s+', '', t)
        return t or None

    def _unwrap(self, n):
        while n is not None and n.type in (
            'parenthesized_expression',
            'non_null_expression',
            'await_expression',
            'type_assertion',
            'as_expression',
            'optional_chain'
        ):
            nn = n.child_by_field_name('expression') or n.child_by_field_name('value')
            if nn is None and n.children:
                nn = n.children[0]
            if nn is None or nn is n:
                break
            n = nn
        return n

    def _deep_find_first(self, n, types: tuple[str, ...]):
        stack = [n]
        while stack:
            x = stack.pop()
            if x.type in types:
                return x
            stack.extend(x.children)
        return None

    def _owner_lookup_and_display(self, owner_text: str | None):
        if not owner_text:
            return None, None
        o = owner_text.strip()
        o = o.replace('?.', '.')
        o = re.sub(r'\s+', ' ', o)
        o = re.sub(r'\(\)$', '', o)
        if o == 'this':
            return 'this', 'this'
        if o == 'super':
            return 'super', 'super'
        if o.startswith('this.'):
            rest = o[len('this.'):]
            head = re.split(r'[\.\[\(]', rest)[0]
            return head, f"this.{head}"
        if o.startswith('super.'):
            rest = o[len('super.'):]
            head = re.split(r'[\.\[\(]', rest)[0]
            return head, f"super.{head}"
        head = re.split(r'[\.\[\(]', o)[0]
        return head, o

    # ---------------- Types / membros ----------------
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
        return 'interface' if node.type == 'interface_declaration' else 'class'

    def get_type_name(self, node, src: bytes):
        for ch in node.children:
            if ch.type in ('identifier', 'type_identifier', 'class_identifier'):
                return get_node_text(ch, src)
        nm = node.child_by_field_name('name')
        if nm is not None:
            return get_node_text(nm, src)
        return None

    def find_fields(self, type_node, src: bytes):
        fields: dict[str, str | None] = {}

        def add_field(name: str | None, typ: str | None):
            if name:
                fields[name] = typ

        # Propriedades do corpo + parâmetros-propriedade do construtor
        def visit_class(n):
            if n.type == 'class_body':
                for m in n.children:
                    if m.type in ('field_definition', 'public_field_definition', 'property_definition'):
                        name, tann_txt = None, None
                        for s in m.children:
                            if s.type in ('identifier', 'property_identifier'):
                                name = get_node_text(s, src)
                            elif s.type == 'type_annotation':
                                tann_txt = get_node_text(s, src)
                        add_field(name, self._base_type_from_annotation_text(tann_txt or ""))

                    is_ctor = False
                    if m.type == 'constructor':
                        is_ctor = True
                    elif m.type == 'method_definition':
                        for s in m.children:
                            if s.type in ('property_identifier', 'identifier') and get_node_text(s, src) == 'constructor':
                                is_ctor = True
                                break
                    if is_ctor:
                        params = m.child_by_field_name('parameters')
                        if params:
                            for p in params.children:
                                if p.type in ('required_parameter', 'optional_parameter', 'parameter'):
                                    ptxt = get_node_text(p, src)
                                    if re.search(r'\b(public|private|protected|readonly)\b', ptxt):
                                        ident = self._deep_find_first(p, ('identifier',))
                                        name = get_node_text(ident, src) if ident is not None else None
                                        tann = self._deep_find_first(p, ('type_annotation',))
                                        tann_txt = get_node_text(tann, src) if tann is not None else None
                                        add_field(name, self._base_type_from_annotation_text(tann_txt or ""))

            for c in n.children:
                visit_class(c)

        def visit_interface(n):
            if n.type == 'object_type':
                for m in n.children:
                    if m.type == 'property_signature':
                        name = None
                        for s in m.children:
                            if s.type in ('property_identifier', 'identifier'):
                                name = get_node_text(s, src)
                                break
                        add_field(name, None)
            for c in n.children:
                visit_interface(c)

        if type_node.type == 'class_declaration':
            visit_class(type_node)
        else:
            visit_interface(type_node)
        return fields

    def find_methods(self, type_node, src: bytes):
        methods = []
        def visit_body(n):
            if n.type == 'class_body':
                for m in n.children:
                    if m.type == 'method_definition':
                        for s in m.children:
                            if s.type in ('property_identifier', 'identifier'):
                                methods.append(get_node_text(s, src))
                    elif m.type == 'constructor':
                        methods.append('constructor')
            elif n.type == 'object_type':
                for m in n.children:
                    if m.type == 'method_signature':
                        for s in m.children:
                            if s.type in ('property_identifier', 'identifier'):
                                methods.append(get_node_text(s, src))
            for ch in n.children:
                visit_body(ch)
        for ch in type_node.children:
            visit_body(ch)
        return methods

    # ---------------- Chamadas ----------------
    def _owner_from_callee(self, callee, src: bytes) -> str | None:
        callee = self._unwrap(callee)
        if callee is None:
            return None
        if callee.type in ('member_expression', 'optional_member_expression'):
            obj = self._unwrap(callee.child_by_field_name('object'))
            if obj is None:
                return None
            # Se a base ainda for chamada, desce até o objeto base
            if obj.type == 'call_expression':
                inner = obj.child_by_field_name('function')
                if inner is not None:
                    return self._owner_from_callee(inner, src)
            return get_node_text(obj, src)
        if callee.type == 'subscript_expression':
            obj = self._unwrap(callee.child_by_field_name('object'))
            return get_node_text(obj, src) if obj is not None else None
        if callee.type in ('identifier', 'property_identifier'):
            return None
        if callee.type == 'call_expression':
            inner = callee.child_by_field_name('function')
            if inner is not None:
                return self._owner_from_callee(inner, src)
        return None

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if node.type != 'call_expression':
            text = get_node_text(node, src)
            return _regex_owner_method(text)

        fn = node.child_by_field_name('function')
        if fn is None:
            text = get_node_text(node, src)
            return _regex_owner_method(text)

        fn = self._unwrap(fn)
        # member/optional member: method é a propriedade mais à direita; owner é o objeto desse member
        if fn.type in ('member_expression', 'optional_member_expression'):
            obj = self._unwrap(fn.child_by_field_name('object'))
            prop = fn.child_by_field_name('property')
            if obj is None or prop is None:
                return None, None
            method = get_node_text(prop, src)
            # Se owner for resultado de uma chamada, reduza ao objeto base dessa chamada
            if obj.type == 'call_expression':
                inner = obj.child_by_field_name('function')
                owner_text = self._owner_from_callee(inner, src) if inner is not None else get_node_text(obj, src)
            else:
                owner_text = get_node_text(obj, src)
            return owner_text, method

        # subscript: a[b]() -> owner ~ a, method desconhecido
        if fn.type == 'subscript_expression':
            obj = self._unwrap(fn.child_by_field_name('object'))
            return (get_node_text(obj, src) if obj is not None else None), None

        # chamada de identificador simples
        if fn.type in ('identifier', 'property_identifier'):
            return None, get_node_text(fn, src)

        # fallback
        text = get_node_text(node, src)
        return _regex_owner_method(text)

    def find_method_invocations(self, anchor_node, src: bytes, fields: dict, imported: list, methods: list, inv=None):
        if inv is None:
            inv = []
        seen = set()
        class_name = self.get_type_name(anchor_node, src)
        fields_norm = {(k or '').strip(): v for k, v in (fields or {}).items()}
        imported_set = set(imported or [])
        known_globals = {
            'JSON', 'console', 'window', 'document', 'sessionStorage', 'localStorage',
            'Math', 'Number', 'String', 'Object', 'Array', 'Date'
        }

        stack = [anchor_node]
        while stack:
            n = stack.pop()
            if n.type == 'call_expression':
                key = (n.start_byte, n.end_byte)
                if key in seen:
                    stack.extend(n.children)
                    continue
                seen.add(key)

                owner_raw, method = self.extract_owner_and_method_from_call(n, src)
                lookup_key, display_owner = self._owner_lookup_and_display(owner_raw)

                owner_type = 'unknown'
                owner_class = None

                # Método da própria classe: this.foo() ou foo()
                if method and method in (methods or []) and (lookup_key is None or lookup_key in ('this', 'super')):
                    owner_type = 'instance'
                    owner_class = class_name
                    display_owner = 'this'

                # Campo da classe (this.<campo>)
                elif lookup_key in fields_norm:
                    owner_type = 'instance'
                    owner_class = fields_norm[lookup_key]
                    display_owner = f"this.{lookup_key}"

                # Função importada chamada diretamente: saveSegmentData(...)
                elif (lookup_key is None or lookup_key == '') and method and method in imported_set:
                    owner_type = 'class'
                    owner_class = method
                    display_owner = method

                # Dono é um identificador importado (ex.: Namespace.fn())
                elif lookup_key in imported_set:
                    owner_type = 'class'
                    owner_class = lookup_key

                # Globais do runtime
                elif lookup_key in known_globals:
                    owner_type = 'class'
                    owner_class = lookup_key

                inv.append({
                    "owner": display_owner if display_owner else (lookup_key or owner_raw),
                    "owner_type": owner_type,
                    "owner_class": owner_class,
                    "method": method
                })

            stack.extend(n.children)
        return inv
