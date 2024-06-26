import ast
from ast import (
    Assign,
    Attribute,
    Call,
    ClassDef,
    FunctionDef,
    Load,
    Name,
    Return,
    Tuple,
    expr,
    walk,
)
from typing import Any
from vpy.typechecker.pyanalyze.value import UnboundMethodValue

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.rewrite import RewriteName
from vpy.lib.utils import (
    annotation_from_type_value,
    is_field,
    is_obj_attribute,
    parse_class,
    typeof_node,
)


class AliasVisitor(ast.NodeVisitor):
    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        v_from: VersionId,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_from = v_from
        self.aliases: dict[expr, Attribute | None] = {}

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        for expr in node.body:
            self.visit(expr)
        return node

    def visit_Assign(self, node: Assign) -> Any:
        def __collect_ref(alias: ast.expr, n: Attribute):
            obj_type = annotation_from_type_value(typeof_node(n.value))
            if is_field(
                n,
                self.env.fields[obj_type][self.v_from],
            ):
                self.aliases[alias] = n
                return True
            return False

        found_refs = False
        self.visit(node.value)
        for t in node.targets:
            self.visit(t)
        # TODO : Fix this
        if isinstance(node.value, Tuple):
            for el in node.value.elts:
                if el in self.aliases:
                    self.aliases[node.targets[0]] = self.aliases[el]
                    found_refs = True
                if isinstance(el, Attribute):
                    found_refs = __collect_ref(node.targets[0], el)
        elif isinstance(node.value, Attribute) or isinstance(node.value, Name):
            if node.value in self.aliases:
                self.aliases[node.targets[0]] = self.aliases[node.value]
                found_refs = True
            elif isinstance(node.value, Attribute):
                found_refs = __collect_ref(node.targets[0], node.value)
        # TODO: Check if function returns a reference or an alias
        elif isinstance(node.value, Call):
            call_t = typeof_node(node.value.func)
            if isinstance(call_t, UnboundMethodValue) and isinstance(
                call_t.composite.value.get_type(), type
            ):
                cls = call_t.composite.value.get_type()
                import sys

                mod = sys.modules[cls.__module__]
                cls_ast, g = parse_class(mod, cls)
                # m[0]()
                # a = self.change
                # a()
                # TODO: Fix this
                obj_type = annotation_from_type_value(
                    typeof_node(
                        node.value.func.value
                        if isinstance(node.value.func, Attribute)
                        else node.value.func
                    )
                )
                mname = (
                    node.value.func.attr
                    if isinstance(node.value.func, Attribute)
                    else node.value.func.id
                )
                try:
                    method = next(
                        m.implementation
                        for m in self.env.methods[obj_type][self.v_from]
                        if m.name == mname
                    )
                    visitor = AliasVisitor(g, cls_ast, self.env, self.v_from)
                    rw_visitor = RewriteName(
                        src=Name(id=method.args.args[0].arg, ctx=Load()),
                        target=node.value.func.value,
                    )
                    method = rw_visitor.visit(method)
                    visitor.visit(method)
                    for expr in method.body:
                        if isinstance(expr, Return):
                            for e in walk(expr):
                                if e in visitor.aliases:
                                    self.aliases[node.targets[0]] = visitor.aliases[e]
                                    found_refs = True
                                elif isinstance(e, Attribute):
                                    e_type = annotation_from_type_value(
                                        typeof_node(e.value)
                                    )
                                    if e_type in self.env.fields and is_field(
                                        e,
                                        self.env.fields[e_type][self.v_from],
                                    ):
                                        self.aliases[node.targets[0]] = e

                                        found_refs = True
                except StopIteration:
                    pass
        if (
            isinstance(node.targets[0], Attribute)
            and not found_refs
            and not is_obj_attribute(node.targets[0])
        ):
            self.aliases[node.targets[0]] = None

    def visit_Call(self, node: Call):
        if isinstance(node.func, Attribute):
            self.visit(node.func.value)
        else:
            self.generic_visit(node)

    def visit_Attribute(self, node: Attribute):
        # TODO: Revise this
        if isinstance(node.ctx, Load):
            existing = [
                n
                for n in self.aliases.keys()
                if isinstance(n, Attribute) and ast.unparse(node) == ast.unparse(n)
            ]
            if existing:
                existing_node = existing[-1]
                if self.aliases[existing_node] is not None:
                    self.aliases[node] = self.aliases[existing_node]
            else:
                self.aliases[node] = node
        self.generic_visit(node)

    def visit_Name(self, node: Name) -> Any:
        if isinstance(node.ctx, Load):
            existing = [
                n
                for n in self.aliases.keys()
                if isinstance(n, Name) and n.id == node.id
            ]
            if existing:
                existing_node = existing[-1]
                if self.aliases[existing_node] is not None:
                    self.aliases[node] = self.aliases[existing_node]
