from ast import (
    Assign,
    Attribute,
    BinOp,
    Call,
    ClassDef,
    Expr,
    List,
    Name,
    Subscript,
    Tuple,
    keyword,
)
import copy
from vpy.lib.lib_types import Environment, FieldName, Graph, VersionId
from vpy.lib.transformers.lens import PutLens
from vpy.lib.utils import (
    FieldReferenceCollector,
    fields_in_function,
    fresh_var,
    get_at,
    get_obj_attribute,
    is_field,
    is_obj_attribute,
)
import ast


class AssignTransformer(ast.NodeTransformer):
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

    def step_rw_assign(
        self, target: Attribute, value: ast.expr | None, lens_ver
    ) -> list[ast.Expr]:
        exprs = []
        visitor = copy.deepcopy(self)
        visitor.v_target = lens_ver
        visitor.v_from = self.v_from
        rw_exprs = visitor.rw_assign(target, value)
        visitor.v_from = lens_ver
        visitor.v_target = self.v_target
        for expr in rw_exprs:
            exprs.extend(visitor.visit(expr))
        return exprs

    def rw_assign(self, lhs: Attribute, rhs: ast.expr | None) -> list[ast.Expr]:
        """
        Rewrite an assignment to an object field (from which class?) in another version.
        """
        if rhs is None:
            assert False
        # TODO: Iterate over lenses of class type(target.attr)
        exprs = []
        for field in self.env.get_lenses[self.v_target]:
            lens_node = self.env.get_lenses[self.v_target][field][self.v_from]
            lens_ver = get_at(lens_node)
            # Case for transitive lenses
            if lens_ver != self.v_from:
                exprs = self.step_rw_assign(lhs, rhs, lens_ver)
            #
            elif len(fields_in_function(lens_node, {FieldName(lhs.attr)})) > 0:
                # Change field name to lens method call
                self_attr = get_obj_attribute(
                    obj=lhs.value,
                    attr=lens_node.name,
                    obj_type=lhs.value.inferred_value,
                    attr_type=lens_node.inferred_value,
                )
                # Add right-hand side of assignment as argument
                keywords = [keyword(arg=lhs.attr, value=rhs)]
                # Add fields referenced in lens as arguments
                # TODO: This function call should only lookup fields from this class? Look only for self?
                # TODO: Use type of target.attr as key for class name
                obj_type = lhs.value.inferred_value.get_type().__name__
                references = fields_in_function(
                    lens_node, self.env.fields[obj_type][self.v_from]
                )
                for ref in references:
                    if ref != lhs.attr:
                        attr = get_obj_attribute(
                            obj=lhs.value,
                            attr=ref,
                            obj_type=lhs.value.inferred_value,
                        )
                        attr = self.visit(attr)
                        keywords.append(keyword(arg=ref, value=attr))

                self_call = Call(func=self_attr, args=[], keywords=keywords)

                # add put lens definition if missing
                if (self.v_from, self.v_target) not in self.env.put_lenses:
                    obj_type = lhs.value.inferred_value.get_type().__name__
                    put_lens = PutLens(self.env.fields[obj_type][self.v_from]).visit(
                        copy.deepcopy(lens_node)
                    )
                    self.env.put_lenses[(self.v_from, self.v_target)] = put_lens
                    self.cls_ast.body.append(put_lens)

                # Rewrite assignment using put lens
                lens_target = get_obj_attribute(
                    obj=lhs.value,
                    attr=field,
                    ctx=ast.Store(),
                    obj_type=lhs.value.inferred_value,
                )
                lens_assign = Assign(targets=[lens_target], value=self_call)
                ast.fix_missing_locations(lens_assign)
                exprs.append(Expr(lens_assign))
        return exprs

    def visit_AugAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
            node.target, self.env.fields[self.v_from]
        ):
            left_node = copy.deepcopy(node.target)
            left_node.ctx = ast.Load()
            unfold = BinOp(left=left_node, right=node.value, op=node.op)
            unfold = self.visit(unfold)
            assign = Assign(targets=[node.target], value=unfold)
            exprs = self.rw_assign(node.target, assign.value)
            if len(exprs) > 0:
                return exprs
        return node

    def visit_AnnAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
            node.target, self.env.fields[self.v_from]
        ):
            return self.rw_assign(node.target, node.value)
        return node

    def visit_Assign(self, node):
        exprs = []

        # Rewrite right-hand side of assignment.
        node.value = self.visit(node.value)

        # Collect all field references in left-hand side of assignment.
        target_references = set()

        def __collect_ref(node: Attribute) -> set[str]:
            n = node
            if isinstance(node, Subscript):
                n = n.value
            if isinstance(n, Attribute):
                # TODO: Fix this. What fields are we looking for? Only from this class?
                obj_type = n.value.inferred_value.get_type().__name__
                visitor = FieldReferenceCollector(
                    self.env.fields[obj_type][self.v_from]
                )
                visitor.visit(n)
                return visitor.references
            return set()

        for target in node.targets:
            if isinstance(target, Subscript):
                target_references = target_references.union(__collect_ref(target.value))

            if isinstance(target, Tuple) or isinstance(target, List):
                for el_target in target.elts:
                    target_references = target_references.union(
                        __collect_ref(el_target)
                    )
            if isinstance(target, Attribute):
                target_references = target_references.union(__collect_ref(target))

        # If any exist, we need to rewrite the assignment. We create a fresh
        # var to store the right-hand side of the assignment since a single
        # assignment may be rewritten to a set of assignment (i.e. all fields
        # affected)
        if len(target_references) > 0:
            local_var = Name(id=fresh_var(), ctx=ast.Store())
            local_assign = Assign(targets=[local_var], value=node.value)
            exprs.append(local_assign)
            node.value = local_var

        for target in node.targets:
            if isinstance(target, Attribute) and is_obj_attribute(target):
                exprs += self.rw_assign(target, node.value)
            # Local variable introduction. We do not rewrite this expressions,
            # just extract it out of multiple assignment.
            elif (
                isinstance(target, Subscript)
                and isinstance(target.value, Attribute)
                and is_obj_attribute(target.value)
            ):
                local_var = Name(id=fresh_var(), ctx=ast.Store())
                local_assign = Assign(targets=[local_var], value=target.value)
                exprs.append(local_assign)
                node_copy = copy.deepcopy(target)
                node_copy.value = local_var
                local_assign = Assign(targets=[node_copy], value=node.value)
                exprs.append(local_assign)
                for e in self.rw_assign(target.value, local_var):
                    exprs.append(e)
            elif isinstance(target, Name):
                node_copy = copy.deepcopy(node)
                node_copy.targets = [target]
                exprs.append(node_copy)
            elif isinstance(target, Tuple) or isinstance(target, List):
                fields = []
                for el in target.elts:
                    if (
                        isinstance(el, Attribute)
                        and is_obj_attribute(el)
                        and is_field(
                            el,
                            self.env.fields[
                                el.value.inferred_value.get_type().__name__
                            ][self.v_from],
                        )
                    ):
                        fields.append(el)
                if len(fields) == 0:
                    exprs.append(node)
                else:
                    # local_tuple_var = Name(id=fresh_var(), ctx=ast.Store())
                    # local_tuple_assign = Assign(
                    #     targets=[local_tuple_var], value=node.value
                    # )
                    # # TODO: check if this makes sense
                    # # local_tuple_var.inferred_value = node.value.inferred_value
                    # exprs.append(local_tuple_assign)
                    for index, el in enumerate(target.elts):
                        val = Subscript(
                            value=node.value, slice=ast.Constant(value=index)
                        )
                        if el in fields:
                            el = self.rw_assign(el, val)
                            exprs += el
                        else:
                            exprs.append(Assign(targets=[el], value=val))
            elif isinstance(target, ast.List):
                assert False
        return exprs
