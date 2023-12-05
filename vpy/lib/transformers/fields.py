import ast
import copy
from ast import Attribute, Call, ClassDef

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    get_at,
    get_obj_attribute,
    has_get_lens,
    is_obj_attribute,
)

from pyanalyze.value import KnownValue


class FieldTransformer(ast.NodeTransformer):
    """
    Transformer to rewrite field load expressions of the form obj.field
    from version v_from to version v_target.
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
        if not (is_obj_attribute(node) and isinstance(node.ctx, ast.Load)):
            node = self.generic_visit(node)
            return node
        obj_type = node.value.inferred_value
        if isinstance(obj_type, KnownValue):
            obj_type = node.value.inferred_value.val
        else:
            obj_type = node.value.inferred_value.get_type()
        if obj_type.__name__ not in self.env.fields:
            return node
        else:
            lens = self.env.get_lenses.get(
                v_from=self.env.bases[self.v_from],
                field_name=node.attr,
                v_to=self.env.bases[self.v_target],
            )
            if lens is None:
                assert False
            lens_node = lens.node
            self_attr = get_obj_attribute(
                obj=node.value,
                attr=lens_node.name,
                obj_type=node.value.inferred_value,
                attr_type=node.inferred_value,
            )
            self_call = Call(func=self_attr, args=[], keywords=[])
            self_call.inferred_value = node.value.inferred_value
            if not has_get_lens(self.cls_ast, lens_node):
                from vpy.lib.transformers.cls import MethodTransformer

                lens_node_copy = copy.deepcopy(lens_node)
                visitor = MethodTransformer(
                    g=self.g,
                    cls_ast=self.cls_ast,
                    env=self.env,
                    target=self.v_target,
                )
                if get_at(lens_node_copy) != self.v_target:
                    lens_node_copy = visitor.visit(lens_node_copy)
                self.cls_ast.body.append(lens_node_copy)

            node = self_call
        return node

    def visit_Call(self, node: Call):
        for index, arg in enumerate(node.args):
            node.args[index] = self.visit(arg)
        for index, kw in enumerate(node.keywords):
            node.keywords[index].value = self.visit(kw.value)
        if isinstance(node.func, Attribute):
            node.func.value = self.visit(node.func.value)
        return node
