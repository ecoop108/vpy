import ast
from ast import Attribute, Call, ClassDef, FunctionDef, Load, Name
from typing import Any

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.rewrite import RewriteName
from vpy.lib.utils import create_obj_attr


class MethodLensTransformer(ast.NodeTransformer):
    """
    Rewrite method call of the form obj.m(*args, **kwargs) using method lenses from version v_from to version v_target.
    """

    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        v_target: VersionId,
        v_from: VersionId,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_target = v_target
        self.v_from = v_from

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
        for expr in node.body:
            expr = self.visit(expr)
        return node

    def visit_Call(self, node: Call) -> Call:
        from vpy.lib.transformers.cls import MethodTransformer

        method_lens = None
        # Rewrite method name to lens node name
        if isinstance(node.func, Name):
            if isinstance(node.func.inferred_value.get_type(), type):
                method_lens = self.env.method_lenses.get(
                    self.v_from,
                    v_to=self.v_target,
                    field_name="__init__",
                )
                if method_lens:
                    node.func = Name(id=method_lens.node.name, ctx=Load())

        if isinstance(node.func, Attribute):
            method_lens = self.env.method_lenses.get(
                self.v_from,
                v_to=self.v_target,
                field_name=node.func.attr,
            )
            if method_lens:
                node.func.attr = method_lens.node.name

        # Rewrite and add lens node to class body
        if method_lens and not hasattr(method_lens.node, "added"):
            # Rewrite lens body to version v_target
            method_visitor = MethodTransformer(
                self.g, self.cls_ast, self.env, self.v_target
            )
            method_visitor.visit(method_lens.node)
            # Replace second param in body with call to method in version v_from
            obj_arg = method_lens.node.args.args[0]
            method_arg = method_lens.node.args.args.pop(1)
            rw_visitor = RewriteName(
                src=Name(id=method_arg.arg, ctx=Load()),
                target=create_obj_attr(
                    obj=Name(id=obj_arg.arg, ctx=Load()),
                    attr=method_lens.field,
                    obj_type=self.cls_ast.inferred_value,
                ),
            )
            lens_node = rw_visitor.visit(method_lens.node)
            self.cls_ast.body.append(lens_node)
            method_lens.node.added = True

        return node
