import ast
from ast import Attribute, Call, ClassDef, FunctionDef, Load, Name, Return, keyword
from copy import deepcopy

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.rewrite import RewriteName
from vpy.lib.utils import (
    annotation_from_type_value,
    create_obj_attr,
    get_at,
    is_lens,
    typeof_node,
)


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
        from vpy.lib.transformers.cls import MethodTransformer

        if is_lens(node):
            return node

        method_lens = self.env.method_lenses[self.cls_ast.name].find_lens(
            v_from=self.v_target, v_to=self.v_from, attr=node.name
        )
        node_copy = node
        mdef = next(
            (
                m
                for m in self.env.methods[self.cls_ast.name][self.v_target]
                if m.name == node.name
            ),
            None,
        )
        if mdef is None:
            assert False
        if method_lens is None or method_lens.node is None:
            return node
        if mdef.interface not in self.cls_ast.body:
            mdef_copy = deepcopy(mdef.interface)
            self_attr = create_obj_attr(
                obj=Name(id="self", ctx=Load()),
                attr=method_lens.node.name,
                obj_type=typeof_node(self.cls_ast),
                attr_type=typeof_node(method_lens.node),
            )
            args = [ast.arg(arg=a.arg) for a in mdef_copy.args.args[1:]]
            kw_args = [
                keyword(arg=kw, value=Name(id=kw)) for kw in mdef_copy.args.kwonlyargs
            ]
            method_lens_call = Call(func=self_attr, args=args, keywords=kw_args)
            mdef_copy.body = [Return(value=method_lens_call)]
            self.cls_ast.body.append(mdef_copy)

        while method_lens is not None and method_lens.node is not None:
            node_copy = deepcopy(node)
            node_copy.name = f"__{method_lens.v_target}__" + node.name

            if not hasattr(method_lens.node, "added"):
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
                        attr=node_copy.name,
                        obj_type=typeof_node(self.cls_ast),
                    ),
                )
                lens_node = rw_visitor.visit(method_lens.node)
                self.cls_ast.body.append(lens_node)
                method_lens.node.added = True
                method_lens = self.env.method_lenses[self.cls_ast.name].find_lens(
                    v_from=method_lens.v_target, v_to=self.v_from, attr=node.name
                )
        node = node_copy
        for expr in node.body:
            self.visit(expr)

        return node

    def visit_Call(self, node: Call) -> Call:
        """
        Rewrite method call of the form obj.m(*args, **kwargs) using method
        lenses from version v_from to version v_target.
        """
        from vpy.lib.transformers.cls import MethodTransformer

        method_lens = None
        # Rewrite method name to lens node name
        if isinstance(node.func, Name):
            if isinstance(typeof_node(node.func).get_type(), type):
                if node.func.id in self.env.method_lenses:
                    method_lens = self.env.method_lenses[node.func.id].find_lens(
                        v_from=self.v_from,
                        v_to=self.v_target,
                        attr="__init__",
                    )
                    if method_lens and method_lens.node:
                        node.func = Name(id=method_lens.node.name, ctx=Load())
                        node.func.inferred_value = method_lens.node.inferred_value

        # Rewrite object method call (`obj.m(...)`) using its corresponding lens.
        # This is required whenever the definition of `m` at version `v_from` is
        # different from that of version `v_target`
        if isinstance(node.func, Attribute):
            obj_type = annotation_from_type_value(typeof_node(node.func.value))
            if obj_type in self.env.method_lenses:
                lenses = self.env.get_lenses[obj_type]
                # Make sure that we are not rewriting a lens call.
                if node.func.attr not in [
                    l.node.name
                    for t in lenses.values()
                    for w in t.values()
                    for l in w.values()
                    if l.node is not None
                ]:
                    method_v_from = next(
                        m.implementation
                        for m in self.env.methods[obj_type][self.v_from]
                        if m.name == node.func.attr
                    )
                    method_lens = self.env.method_lenses[obj_type].find_lens(
                        v_from=self.v_from,
                        v_to=self.v_target,
                        attr=node.func.attr,
                    )
                    if get_at(method_v_from) == self.v_from:
                        node.func.attr = f"__{self.v_from}_{method_v_from.name}"
                    if method_lens is not None and method_lens.node is not None:
                        node.func.attr = method_lens.node.name

        # Rewrite and add lens node to class body
        if (
            method_lens is not None
            and method_lens.node is not None
            and not hasattr(method_lens.node, "added")
        ):
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
                    attr=method_lens.attr,
                    obj_type=typeof_node(self.cls_ast),
                ),
            )
            lens_node = rw_visitor.visit(method_lens.node)
            self.cls_ast.body.append(lens_node)
            method_lens.node.added = True

        return node
