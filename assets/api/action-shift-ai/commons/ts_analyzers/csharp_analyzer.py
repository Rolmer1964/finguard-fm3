import re
from typing import Optional, Dict, List, Tuple

from commons.ts_analyzers.base_analyzer import (
    BaseAnalyzer,
    get_node_text,
    _regex_owner_method,
)


class CSharpAnalyzer(BaseAnalyzer):
    language_name = "c_sharp"

    # ----------------------- Helpers -----------------------
    def _norm_type(self, type_text: str) -> str:
        """
        Normaliza o texto do tipo para uma forma simples:
        - remove modificadores (ref/out/in/params)
        - remove prefixo global::
        - remove sufixo nullable '?'
        - remove sufixos de array []
        - remove parâmetros genéricos <> (mantém identificador base)
        - mantém apenas o último identificador se for qualificado por '.'
        """
        if not type_text:
            return type_text

        t = type_text.strip()
        t = re.sub(r"^(?:ref|out|in|params)\s+", "", t)
        t = re.sub(r"^global::", "", t)
        t = re.sub(r"\?$", "", t)
        t = re.sub(r"(\[\s*\])+$", "", t)

        # remove blocos genéricos (de forma iterativa para casos aninhados)
        prev = None
        while prev != t and "<" in t and ">" in t:
            prev = t
            t = re.sub(r"<[^<>]*?>", "", t)

        # pega apenas o último segmento qualificado
        if "." in t:
            t = t.split(".")[-1]

        return t

    def _get_identifier_text(self, node, src: bytes) -> Optional[str]:
        if node is None:
            return None

        name = node.child_by_field_name("name")
        if name is not None and name.type == "identifier":
            return get_node_text(name, src)

        ident = None
        for ch in node.children:
            if ch.type == "identifier":
                ident = ch
        return get_node_text(ident, src) if ident is not None else None

    def _get_method_name_from_invocation_target(self, name_node, src: bytes) -> Optional[str]:
        if name_node is None:
            return None

        if name_node.type == "identifier":
            return get_node_text(name_node, src)

        # generic_name -> contém identifier interno
        if name_node.type == "generic_name":
            ident = name_node.child_by_field_name("name")
            if ident is None:
                for ch in name_node.children:
                    if ch.type == "identifier":
                        ident = ch
                        break
            return get_node_text(ident, src) if ident is not None else get_node_text(name_node, src)

        # outros casos: retorna texto cru
        return get_node_text(name_node, src)

    # ----------------------- Usings -----------------------
    def find_imported_identifiers(self, root, src: bytes) -> List[str]:
        """
        Retorna uma lista com:
        - Aliases de using_alias_directive
        - Último segmento dos 'using' comuns e 'using static'
        Suporta 'global using'.
        Busca por toda a árvore (DFS).
        """
        names: List[str] = []

        def visit(n):
            if n.type in ("using_directive", "using_alias_directive"):
                text = get_node_text(n, src).strip()
                m = re.search(r"^(?:global\s+)?using\s+(.+?);$", text)
                if not m:
                    # continua DFS
                    for c in n.children:
                        visit(c)
                    return
                body = m.group(1).strip()

                if "=" in body:
                    # using Alias = Namespace.Type;
                    alias = body.split("=", 1)[0].strip()
                    if alias:
                        names.append(alias)
                else:
                    # using static System.Console; | using System.Linq;
                    if body.startswith("static "):
                        body = body[len("static ") :].strip()
                    last = body.split(".")[-1].strip()
                    if last:
                        names.append(last)

            for c in n.children:
                visit(c)

        visit(root)
        return names

    # ----------------------- Types -----------------------
    def find_type_nodes(self, root) -> List:
        """
        Encontra nodes de tipos principais (classe, interface, struct, record, enum).
        """
        nodes: List = []

        def visit(n):
            if n.type in (
                "class_declaration",
                "interface_declaration",
                "struct_declaration",
                "record_declaration",
                "record_struct_declaration",
                "enum_declaration",
            ):
                nodes.append(n)
            for c in n.children:
                visit(c)

        visit(root)
        return nodes

    def get_type_kind(self, node) -> str:
        mapping = {
            "class_declaration": "class",
            "interface_declaration": "interface",
            "struct_declaration": "struct",
            "record_declaration": "record",
            "record_struct_declaration": "record_struct",
            "enum_declaration": "enum",
        }
        return mapping.get(node.type, node.type)

    def get_type_name(self, node, src: bytes) -> Optional[str]:
        """
        Extrai o identifier do tipo (ex.: class Foo<T> -> 'Foo')
        """
        for ch in node.children:
            if ch.type == "identifier":
                return get_node_text(ch, src)
        return None

    # ----------------------- Fields / Properties / Primary-ctor -----------------------
    def find_fields(self, type_node, src: bytes) -> Dict[str, str]:
        """
        Retorna um dicionário nome->tipo normalizado para:
        - Parâmetros do primary constructor (C# 12) em class_declaration.
        - field_declaration (via variable_declaration).
        - property_declaration (consideradas como campos, ex.: auto-properties).
        """
        fields: Dict[str, str] = {}

        def add_field(name_node, type_node_or_text):
            if not name_node or type_node_or_text is None:
                return
            name = get_node_text(name_node, src) if hasattr(name_node, "type") else str(name_node)
            if not name:
                return
            type_text = (
                get_node_text(type_node_or_text, src)
                if hasattr(type_node_or_text, "type")
                else str(type_node_or_text)
            )
            fields[name] = self._norm_type(type_text)

        # 1) Primary constructor parameters (C# 12): class X(type name, ...)
        for ch in type_node.children:
            if ch.type == "parameter_list":
                for p in ch.children:
                    if p.type == "parameter":
                        p_type = p.child_by_field_name("type")
                        p_name = p.child_by_field_name("name")
                        if p_name is None:
                            for sub in p.children:
                                if sub.type == "identifier":
                                    p_name = sub
                                    break
                        if p_name is not None and p_type is not None:
                            add_field(p_name, p_type)

        # 2) Campos (field_declaration)
        def handle_field_declaration(n):
            # field_declaration -> variable_declaration -> type + variable_declarators
            variable_decl = None
            for s in n.children:
                if s.type == "variable_declaration":
                    variable_decl = s
                    break
            if variable_decl is None:
                return

            vtype = variable_decl.child_by_field_name("type")

            decls = variable_decl.child_by_field_name("declarators")
            if decls is None:
                for s in variable_decl.children:
                    if s.type == "variable_declarators":
                        decls = s
                        break

            if decls is None:
                # fallback: um único variable_declarator diretamente
                for s in variable_decl.children:
                    if s.type == "variable_declarator":
                        idn = None
                        for k in s.children:
                            if k.type == "identifier":
                                idn = k
                                break
                        if idn is not None:
                            add_field(idn, vtype)
                return

            # variable_declarators -> variable_declarator -> identifier
            for v in decls.children:
                if v.type == "variable_declarator":
                    idn = None
                    for kid in v.children:
                        if kid.type == "identifier":
                            idn = kid
                            break
                    if idn is not None:
                        add_field(idn, vtype)

        # 3) Propriedades (property_declaration)
        def handle_property_declaration(n):
            ptype = n.child_by_field_name("type")
            pname = n.child_by_field_name("name")
            if pname is None:
                for k in n.children:
                    if k.type == "identifier":
                        pname = k
                        break
            if ptype is not None and pname is not None:
                add_field(pname, ptype)

        # DFS no tipo para pegar fields/propriedades
        stack = [type_node]
        while stack:
            n = stack.pop()
            if n.type == "field_declaration":
                handle_field_declaration(n)
            elif n.type == "property_declaration":
                handle_property_declaration(n)
            stack.extend(n.children)

        return fields

    # ----------------------- Methods -----------------------
    def find_methods(self, type_node, src: bytes) -> List[str]:
        """
        Coleta nomes de métodos (method_declaration) em DFS.
        """
        methods: List[str] = []
        stack = [type_node]
        while stack:
            n = stack.pop()
            if n.type == "method_declaration":
                name = n.child_by_field_name("name")
                if name is not None:
                    methods.append(get_node_text(name, src))
                else:
                    mname = None
                    for ch in n.children:
                        if ch.type == "identifier":
                            mname = ch
                    if mname is not None:
                        methods.append(get_node_text(mname, src))
            stack.extend(n.children)
        return methods

    # ----------------------- Invocation owner/method -----------------------
    def extract_owner_and_method_from_call(self, node, src: bytes) -> Tuple[Optional[str], Optional[str]]:
        """
        Retorna (owner, method) para invocation_expression.
        Suporte:
        - expr.name(...)  -> member_access_expression
        - Method(...)     -> identifier
        - owner?.Name(...) via member_binding_expression dentro de conditional_access_expression
        Fallback: regex quando a estrutura não é reconhecida.
        """
        if node.type != "invocation_expression":
            return None, None

        expr = node.child_by_field_name("expression")
        if expr is None:
            text = get_node_text(node, src)
            owner, method = _regex_owner_method(text)
            return (owner, method) if owner and method else (None, None)

        # owner.name(...)
        if expr.type == "member_access_expression":
            left = expr.child_by_field_name("expression")
            name = expr.child_by_field_name("name")
            if left is not None and name is not None:
                return get_node_text(left, src), self._get_method_name_from_invocation_target(name, src)

        # Method(...)
        if expr.type == "identifier":
            return None, get_node_text(expr, src)

        # owner?.Name(...) -> invocation_expression(expression=member_binding_expression) com pai conditional_access_expression
        if expr.type == "member_binding_expression":
            parent = node.parent
            if parent is not None and parent.type == "conditional_access_expression":
                owner = parent.child_by_field_name("expression")
                name = expr.child_by_field_name("name")
                if owner is not None and name is not None:
                    return get_node_text(owner, src), self._get_method_name_from_invocation_target(name, src)

        # fallback regex
        text = get_node_text(node, src)
        owner, method = _regex_owner_method(text)
        if owner and method:
            return owner, method

        return None, None