from ast import Call, ClassDef
import ast
import copy
from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import get_obj_attribute, has_get_lens, is_obj_field


class FieldTransformer(ast.NodeTransformer):
    """
    Rewrite field access expressions of the form expr.field where expr is an object and field is a field of that object.
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

    def visit_Attribute(self, node):
        # TODO: Review this
        if not (
            is_obj_field(node, {self.cls_ast.name: self.env.fields[self.v_from]})
            and isinstance(node.ctx, ast.Load)
        ):
            node = self.generic_visit(node)
            return node
        lens_node = self.env.get_lenses[self.v_from][node.attr][self.v_target]
        self_attr = get_obj_attribute(
            obj=node.value, attr=lens_node.name, obj_type=node.value.inferred_value
        )
        self_attr.inferred_value = node.inferred_value
        self_call = Call(func=self_attr, args=[], keywords=[])
        if not has_get_lens(self.cls_ast, lens_node):
            from vpy.lib.transformers.lens import MethodTransformer

            lens_node_copy = copy.deepcopy(lens_node)
            visitor = MethodTransformer(
                self.g,
                self.cls_ast,
                self.env.fields,
                self.env.get_lenses,
                self.v_target,
            )
            lens_node_copy = visitor.visit(lens_node)
            self.cls_ast.body.append(lens_node_copy)
        return self_call

    def visit_Call(self, node: Call):
        for index, arg in enumerate(node.args):
            node.args[index] = self.visit(arg)
        for index, kw in enumerate(node.keywords):
            node.keywords[index].value = self.visit(kw.value)
        # if isinstance(node.func.inferred_value, KnownValue) and isinstance(node.func.inferred_value.val, type):
        #     cls = node.func.inferred_value.val
        #     import sys
        #     mod = sys.modules[cls.__module__]
        #     cls_ast, g = parse_class(mod, cls)
        #     print(fields_lookup(g, cls_ast, self.v_from))
        #     for arg in node.args:
        #         print(ast.dump(arg))
        #     print(cls.__module__)
        return node
