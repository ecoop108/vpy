import ast
import copy
from ast import Call, ClassDef

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    annotation_from_type_value,
    get_at,
    create_obj_attr,
    has_get_lens,
    is_obj_attribute,
    set_typeof_node,
    typeof_node,
)


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
        obj_type = annotation_from_type_value(typeof_node(node.value))
        if obj_type not in self.env.fields:
            return node
        else:
            if node.attr not in [
                f.name for f in self.env.fields[obj_type][self.v_from]
            ]:
                return node
            lens = self.env.get_lenses[obj_type].find_lens(
                v_from=self.v_target,
                attr=node.attr,
                v_to=self.v_from,
            )
            if lens is None:
                assert False
            lens_node = lens.node
            # Identity lens
            if lens_node is None:
                return node
            self_attr = create_obj_attr(
                obj=node.value,
                attr=lens_node.name,
                obj_type=typeof_node(node.value),
                attr_type=typeof_node(node),
            )
            self_call = Call(func=self_attr, args=[], keywords=[])
            set_typeof_node(self_call, typeof_node(node.value))
            if not has_get_lens(self.cls_ast, lens_node):
                from vpy.lib.transformers.cls import MethodTransformer

                lens_node_copy = copy.deepcopy(lens_node)
                if get_at(lens_node_copy) != self.v_target:
                    visitor = MethodTransformer(
                        g=self.g,
                        cls_ast=self.cls_ast,
                        env=self.env,
                        target=self.v_target,
                    )
                    lens_node_copy = visitor.visit(lens_node_copy)
                self.cls_ast.body.append(lens_node_copy)

            node = self_call
        return node
