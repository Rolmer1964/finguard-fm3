import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text, _regex_owner_method

# ----------------------- JavaScript -----------------------
class JavaScriptAnalyzer(BaseAnalyzer):
    language_name = 'javascript'

    def find_imported_identifiers(self, root, src: bytes):
        names = []
        for ch in root.children:
            if ch.type == 'import_declaration':
                txt = get_node_text(ch, src)
                # vários formatos:
                # import Default, { A as B, C } from 'm';
                # import { A, B as C } from 'm';
                # import * as NS from 'm';
                # import 'm';
                # Default only: import X from 'm';
                left_match = re.search(r'^\s*import\s+(.+?)\s+from\s+[\'"].+[\'"]\s*;?', txt, re.S)
                if left_match:
                    left = left_match.group(1).strip()
                    if left.startswith('{'):
                        inside = re.search(r'\{(.*)\}', left, re.S)
                        if inside:
                            items = inside.group(1)
                            for tok in items.split(','):
                                tok = tok.strip()
                                if not tok:
                                    continue
                                if ' as ' in tok:
                                    alias = tok.split(' as ', 1)[1].strip()
                                    names.append(alias)
                                else:
                                    names.append(tok)
                    elif left.startswith('*'):
                        m = re.search(r'\*\s+as\s+([A-Za-z_$][\w$]*)', left)
                        if m:
                            names.append(m.group(1))
                    else:
                        # default import; pode ter ", { ... }" depois
                        parts = [p.strip() for p in left.split(',')]
                        if parts:
                            if parts[0]:
                                names.append(parts[0])
                        if len(parts) > 1 and parts[1].startswith('{'):
                            inside = re.search(r'\{(.*)\}', parts[1], re.S)
                            if inside:
                                items = inside.group(1)
                                for tok in items.split(','):
                                    tok = tok.strip()
                                    if not tok:
                                        continue
                                    if ' as ' in tok:
                                        alias = tok.split(' as ', 1)[1].strip()
                                        names.append(alias)
                                    else:
                                        names.append(tok)
                # import 'module'; -> ignorar (side-effect)
        return names

    def find_type_nodes(self, root):
        nodes = []
        def visit(n):
            if n.type == 'class_declaration':
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'class'

    def get_type_name(self, node, src: bytes):
        for ch in node.children:
            if ch.type in ('identifier', 'type_identifier', 'class_identifier'):
                return get_node_text(ch, src)
        return None

    def find_fields(self, type_node, src: bytes):
        fields = {}
        def visit_body(n):
            if n.type == 'class_body':
                for m in n.children:
                    if m.type in ('field_definition', 'public_field_definition', 'property_definition'):
                        # pega o primeiro identificador
                        for s in m.children:
                            if s.type in ('identifier', 'property_identifier'):
                                fields[get_node_text(s, src)] = None
        for ch in type_node.children:
            visit_body(ch)
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
        for ch in type_node.children:
            visit_body(ch)
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        if node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None:
                if fn.type == 'member_expression':
                    obj = fn.child_by_field_name('object')
                    prop = fn.child_by_field_name('property')
                    if obj is not None and prop is not None:
                        return get_node_text(obj, src), get_node_text(prop, src)
                elif fn.type in ('identifier', 'property_identifier'):
                    return None, get_node_text(fn, src)
        text = get_node_text(node, src)
        return _regex_owner_method(text)
