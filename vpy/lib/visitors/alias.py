import ast
from ast import Assign, Attribute, Call, ClassDef, Load, Name, Return, Tuple, walk
import copy
from typing import Any
from pyanalyze.value import UnboundMethodValue
from vpy.lib import lookup

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.rewrite import RewriteName
from vpy.lib.utils import (
    is_field,
    parse_class,
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
        self.aliases = {}

    def visit_Assign(self, node: Assign) -> Any:
        def __collect_ref(alias, n: Attribute):
            if is_field(
                n,
                self.env.fields[n.value.inferred_value.get_type().__name__][
                    self.v_from
                ],
            ):
                self.aliases[alias] = (
                    n.value.inferred_value.get_type().__name__,
                    n,
                )
                return True
            return False

        found_refs = False

        self.visit(node.value)

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
            if isinstance(
                node.value.func.inferred_value, UnboundMethodValue
            ) and isinstance(
                node.value.func.inferred_value.composite.value.get_type(), type
            ):
                cls = node.value.func.inferred_value.composite.value.get_type()
                import sys

                mod = sys.modules[cls.__module__]
                cls_ast, g = parse_class(mod, cls)
                mname = (
                    node.value.func.attr
                    if isinstance(node.value.func, Attribute)
                    else node.value.func.id
                )
                method = lookup._method_lookup(g, cls_ast, m=mname, v=self.v_from)
                if method is not None:
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
                                elif isinstance(e, Attribute) and is_field(
                                    e,
                                    self.env.fields[
                                        e.value.inferred_value.get_type().__name__
                                    ][self.v_from],
                                ):
                                    self.aliases[node.targets[0]] = (
                                        e.value.inferred_value.get_type().__name__,
                                        e,
                                    )
                                    found_refs = True
        if not found_refs:
            self.aliases[node.targets[0]] = None

    def visit_Call(self, node: Call):
        if isinstance(node.func, Attribute):
            self.visit(node.func.value)
        else:
            self.generic_visit(node)

    def visit_Attribute(self, node: Attribute):
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
                self.aliases[node] = (
                    node.value.inferred_value.get_type().__name__,
                    node,
                )

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
