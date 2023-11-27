import ast
import copy
from ast import Attribute, Call, ClassDef, FunctionDef, keyword
from dataclasses import field

from vpy.lib.lib_types import Environment, Field, Graph, VersionId
from vpy.lib.utils import (
    fields_in_function,
    get_at,
    get_obj_attribute,
    has_get_lens,
    is_field,
    is_obj_attribute,
)


class FieldTransformer(ast.NodeTransformer):
    """
    Rewrite field access expressions of the form obj.field from version v_from to version v_target.
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

    def __rw_class_field_step(
        self, attr: Attribute, target: VersionId, lens_node: FunctionDef
    ) -> Call:
        visitor = copy.copy(self)

        visitor.v_target = target
        visitor.v_from = self.v_from

        self_attr = get_obj_attribute(
            obj=attr.value,
            attr=lens_node.name,
            obj_type=attr.value.inferred_value,
            attr_type=lens_node.inferred_value,
        )

        # ## Add right-hand side of assignment as argument
        keywords = []
        # Add fields referenced in lens as arguments
        obj_type = attr.value.inferred_value.get_type().__name__
        references = fields_in_function(
            lens_node, self.env.fields[obj_type][self.v_from]
        )
        for ref in references:
            if ref != attr.attr:
                ref_attr = get_obj_attribute(
                    obj=attr.value,
                    attr=ref,
                    obj_type=attr.value.inferred_value,
                )
                ref_attr = self.visit(ref_attr)
                keywords.append(keyword(arg=ref, value=ref_attr))

        # #self_call = Call(func=self_attr, args=[], keywords=keywords)

        # ## Add put lens definition if missing
        # #if (
        # #    self.env.bases[self.v_from],
        # #    self.env.bases[self.v_target],
        # #) not in self.env.put_lenses:
        # #    obj_type = lhs.value.inferred_value.get_type().__name__
        # #    put_lens = PutLens(self.env.fields[obj_type][self.v_from]).visit(
        # #        copy.deepcopy(lens_node)
        # #    )
        # #    self.env.put_lenses[
        # #        (self.env.bases[self.v_from], self.env.bases[self.v_target])
        # #    ] = put_lens
        # #    self.cls_ast.body.append(put_lens)

        # ## Rewrite assignment using put lens
        # #lens_target = get_obj_attribute(
        # #    obj=lhs.value,
        # #    attr=field,
        # #    ctx=ast.Store(),
        # #    obj_type=lhs.value.inferred_value,
        # #)
        # #lens_assign = Assign(targets=[lens_target], value=self_call)
        # #ast.fix_missing_locations(lens_assign)

        rw_expr = visitor.__rw_class_field(attr=attr)

        visitor.v_from = target
        visitor.v_target = self.v_target
        rw_expr = visitor.visit(rw_expr)

        return rw_expr

    def __rw_class_field(self, attr: Attribute) -> Call:
        lens_node = self.env.get_lenses.get_lens(
            v_from=self.env.bases[self.v_from],
            field_name=attr.attr,
            v_to=self.env.bases[self.v_target],
        )
        if lens_node is None:
            assert False
        lens_ver = get_at(lens_node)
        # Case for transitive lenses
        if lens_ver != self.v_target:
            return self.__rw_class_field_step(
                attr=attr, target=lens_ver, lens_node=lens_node
            )
        else:
            self_attr = get_obj_attribute(
                obj=attr.value, attr=lens_node.name, obj_type=attr.value.inferred_value
            )
            self_attr.inferred_value = attr.inferred_value
            self_call = Call(func=self_attr, args=[], keywords=[])
            self_call.inferred_value = attr.value.inferred_value

            if not has_get_lens(self.cls_ast, lens_node):
                from vpy.lib.transformers.cls import MethodTransformer

                lens_node_copy = copy.deepcopy(lens_node)
                visitor = MethodTransformer(
                    g=self.g,
                    cls_ast=self.cls_ast,
                    env=self.env,
                    target=self.v_target,
                )
                lens_node_copy = visitor.visit(lens_node_copy)
                self.cls_ast.body.append(lens_node_copy)

            return self_call

    #     for field in self.env.get_lenses[self.env.bases[self.v_target]]:
    #         if (
    #             self.env.bases[self.v_from]
    #             not in self.env.get_lenses[self.env.bases[self.v_target]][field]
    #         ):
    #             continue

    #         lens_node = self.env.get_lenses[self.env.bases[self.v_target]][field][
    #             self.env.bases[self.v_from]
    #         ]
    #         #
    #         elif (
    #             len(
    #                 fields_in_function(
    #                     lens_node, {Field(name=attr.attr, type=attr.inferred_value)}
    #                 )
    #             )
    #             > 0
    #         ):
    #             # Change field name to get-lens method call
    #             self_attr = get_obj_attribute(
    #                 obj=attr.value,
    #                 attr=lens_node.name,
    #                 obj_type=attr.value.inferred_value,
    #                 attr_type=lens_node.inferred_value,
    #             )

    # #             # Add right-hand side of assignment as argument
    # #             keywords = [keyword(arg=lhs.attr, value=rhs)]
    # #             # Add fields referenced in lens as arguments
    # #             obj_type = lhs.value.inferred_value.get_type().__name__
    # #             references = fields_in_function(
    # #                 lens_node, self.env.fields[obj_type][self.v_from]
    # #             )
    # #             for ref in references:
    # #                 if ref != lhs.attr:
    # #                     attr = get_obj_attribute(
    # #                         obj=lhs.value,
    # #                         attr=ref,
    # #                         obj_type=lhs.value.inferred_value,
    # #                     )
    # #                     attr = self.visit(attr)
    # #                     keywords.append(keyword(arg=ref, value=attr))

    # #             self_call = Call(func=self_attr, args=[], keywords=keywords)

    # #             # Add put lens definition if missing
    # #             if (
    # #                 self.env.bases[self.v_from],
    # #                 self.env.bases[self.v_target],
    # #             ) not in self.env.put_lenses:
    # #                 obj_type = lhs.value.inferred_value.get_type().__name__
    # #                 put_lens = PutLens(self.env.fields[obj_type][self.v_from]).visit(
    # #                     copy.deepcopy(lens_node)
    # #                 )
    # #                 self.env.put_lenses[
    # #                     (self.env.bases[self.v_from], self.env.bases[self.v_target])
    # #                 ] = put_lens
    # #                 self.cls_ast.body.append(put_lens)

    # #             # Rewrite assignment using put lens
    # #             lens_target = get_obj_attribute(
    # #                 obj=lhs.value,
    # #                 attr=field,
    # #                 ctx=ast.Store(),
    # #                 obj_type=lhs.value.inferred_value,
    # #             )
    # #             lens_assign = Assign(targets=[lens_target], value=self_call)
    # #             ast.fix_missing_locations(lens_assign)
    # #             exprs.append(lens_assign)
    # #     return exprs

    def visit_Attribute(self, node):
        if not (is_obj_attribute(node) and isinstance(node.ctx, ast.Load)):
            node = self.generic_visit(node)
            return node
        elif is_field(
            node,
            self.env.fields[node.value.inferred_value.get_type().__name__][self.v_from],
        ):
            node = self.__rw_class_field(node)
            # lens_node = self.env.get_lenses[self.env.bases[self.v_from]][node.attr][
            #     self.env.bases[self.v_target]
            # ]
            # self_attr = get_obj_attribute(
            #     obj=node.value, attr=lens_node.name, obj_type=node.value.inferred_value
            # )
            # self_attr.inferred_value = node.inferred_value
            # self_call = Call(func=self_attr, args=[], keywords=[])
            # self_call.inferred_value = node.value.inferred_value
            # if not has_get_lens(self.cls_ast, lens_node):
            #     from vpy.lib.transformers.cls import MethodTransformer

            #     lens_node_copy = copy.deepcopy(lens_node)
            #     visitor = MethodTransformer(
            #         g=self.g,
            #         cls_ast=self.cls_ast,
            #         env=self.env,
            #         target=self.v_target,
            #     )
            #     lens_node_copy = visitor.visit(lens_node_copy)
            #     self.cls_ast.body.append(lens_node_copy)

            # node = self_call
        return node

    def visit_Call(self, node: Call):
        for index, arg in enumerate(node.args):
            node.args[index] = self.visit(arg)
        for index, kw in enumerate(node.keywords):
            node.keywords[index].value = self.visit(kw.value)
        if isinstance(node.func, Attribute):
            node.func.value = self.visit(node.func.value)
        return node
