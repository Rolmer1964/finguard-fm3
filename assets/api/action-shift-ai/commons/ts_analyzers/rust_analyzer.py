import re
from commons.ts_analyzers.base_analyzer import BaseAnalyzer, get_node_text, _regex_owner_method

# ----------------------- Rust -----------------------
class RustAnalyzer(BaseAnalyzer):
    language_name = 'rust'

    def find_imported_identifiers(self, root, src: bytes):
        names = []
        def add_token(tok: str):
            tok = tok.strip()
            if tok and tok != 'self' and tok != 'super' and tok != 'crate':
                names.append(tok)
        def visit(n):
            if n.type in ('use_declaration', 'use_declaration_list', 'use_declaration_clause', 'use_item', 'use_declaration_statement'):
                text = get_node_text(n, src)
                # Ex: use std::io::{self, Write};
                # Ex: use crate::foo::Bar as Baz;
                body_m = re.search(r'\buse\b\s+(.+?);', text, re.S)
                if body_m:
                    body = body_m.group(1)
                    # expandir listas { ... }
                    if '{' in body and '}' in body:
                        prefix = body.split('{', 1)[0]
                        inside = body.split('{', 1)[1].rsplit('}', 1)[0]
                        for part in inside.split(','):
                            part = part.strip()
                            if ' as ' in part:
                                alias = part.split(' as ', 1)[1].strip()
                                add_token(alias)
                            else:
                                add_token(part.split('::')[-1])
                    else:
                        if ' as ' in body:
                            alias = body.split(' as ', 1)[1].strip()
                            add_token(alias)
                        else:
                            add_token(body.split('::')[-1])
            for c in n.children:
                visit(c)
        visit(root)
        return list(dict.fromkeys(names))

    def find_type_nodes(self, root):
        nodes = []
        def visit(n):
            if n.type in ('struct_item', 'trait_item'):
                nodes.append(n)
            for c in n.children:
                visit(c)
        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        return 'interface' if node.type == 'trait_item' else 'class'

    def get_type_name(self, node, src: bytes):
        for ch in node.children:
            if ch.type == 'type_identifier' or ch.type == 'identifier':
                return get_node_text(ch, src)
        return None

    def find_fields(self, type_node, src: bytes):
        fields = {}
        # Campos de struct (struct_item -> field_declaration_list -> field_declaration identifier)
        if type_node.type == 'struct_item':
            stack = [type_node]
            while stack:
                n = stack.pop()
                if n.type == 'field_declaration':
                    name = None
                    for c in n.children:
                        if c.type == 'field_identifier' or c.type == 'identifier':
                            name = get_node_text(c, src)
                            break
                    if name:
                        fields[name] = None
                stack.extend(n.children)
        return fields

    def find_methods(self, type_node, src: bytes):
        methods = []
        type_name = self.get_type_name(type_node, src)
        if not type_name:
            return methods
        # Procurar impls daquele tipo
        root = type_node
        while root.parent is not None:
            root = root.parent
        def visit(n):
            if n.type == 'impl_item':
                # checar o tipo alvo do impl
                target = None
                stack2 = [n]
                while stack2:
                    x = stack2.pop()
                    if x.type in ('type_identifier', 'scoped_type_identifier'):
                        target = get_node_text(x, src)
                        break
                    stack2.extend(x.children)
                if target and target.split('::')[-1] == type_name:
                    # funções dentro do impl
                    for c in n.children:
                        if c.type in ('function_item', 'method_item'):
                            for s in c.children:
                                if s.type == 'identifier':
                                    methods.append(get_node_text(s, src))
            for c in n.children:
                visit(c)
        visit(root)
        return methods

    def extract_owner_and_method_from_call(self, node, src: bytes):
        # method call frequentemente: call_expression(function: field_expression(...))
        if node.type == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None:
                if fn.type == 'field_expression':
                    obj = fn.child_by_field_name('value')
                    name = fn.child_by_field_name('field')
                    if obj is not None and name is not None:
                        return get_node_text(obj, src), get_node_text(name, src)
                elif fn.type in ('identifier', 'scoped_identifier'):
                    return None, get_node_text(fn, src).split('::')[-1]
        text = get_node_text(node, src)
        owner, method = _regex_owner_method(text)
        if owner and method:
            return owner, method
        return None, None
