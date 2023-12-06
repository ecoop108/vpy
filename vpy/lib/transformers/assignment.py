from ast import (
    Assign,
    Attribute,
    BinOp,
    Call,
    ClassDef,
    List,
    Name,
    Subscript,
    Tuple,
    keyword,
)
from typing import Any
import copy
from vpy.lib.transformers.lens import PutLens
from vpy.lib.lib_types import (
    Environment,
    Field,
    FieldReference,
    Graph,
    VersionId,
)
from vpy.lib.utils import (
    annotation_from_type_value,
    fields_in_function,
    fresh_var,
    get_at,
    get_obj_attribute,
    is_obj_attribute,
)
import ast


class AssignLhsFieldCollector(ast.NodeVisitor):
    """Collect object field references in targets of an assignment statement."""

    def __init__(self):
        self.__parent = None
        self.references: set[FieldReference] = set()

    def visit_Attribute(self, node: Attribute) -> Any:
        if is_obj_attribute(node):
            parent_node = node if self.__parent is None else self.__parent
            self.references.add(
                FieldReference(
                    node=parent_node,
                    field=Field(name=node.attr, type=node.inferred_value),
                    ref_node=node,
                )
            )
        else:
            assert False

    def visit_Subscript(self, node: Subscript) -> Any:
        self.__parent = node
        self.visit(node.value)
        self.__parent = None

    def visit_Tuple(self, node: Tuple) -> Any:
        for el in node.elts:
            self.__parent = node
            self.visit(el)
            self.__parent = None

    def visit_List(self, node: List) -> Any:
        for el in node.elts:
            self.__parent = node
            self.visit(el)
            self.__parent = None


class AssignTransformer(ast.NodeTransformer):
    """
    Transformer to rewrite expressions that assign values to fields (or aliases)
    of a class from version v_from to version v_target.
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

    def step_rw_assign(
        self, target: Attribute, value: ast.expr, lens_ver
    ) -> list[ast.AST]:
        exprs = []
        visitor = copy.copy(self)
        visitor.v_target = lens_ver
        visitor.v_from = self.v_from
        rw_exprs = visitor.__rw_assign(target, value)
        visitor.v_from = lens_ver
        visitor.v_target = self.v_target
        for expr in rw_exprs:
            exprs.extend(visitor.visit(expr))
        return exprs

    def __rw_assign(self, lhs: Attribute, rhs: ast.expr) -> list[ast.AST]:
        """
        Rewrite a simple assignment statement of the form lhs = rhs (where lhs
        is an object field) from version self.v_from to version self.v_target.
        """
        exprs: list[ast.AST] = []

        # Get first component of path between v_from and v_target
        step_lens = self.env.get_lenses.get(
            v_from=self.v_from,
            field_name=lhs.attr,
            v_to=self.v_target,
        )
        # TODO: Typechecker should prevent this case.
        if step_lens is None:
            assert False

        step_target = get_at(step_lens.node)
        # Iterate over lenses from step_target to v_from
        # to detect which attributes are affected
        # by a change to the field in lhs
        for field, lenses in self.env.get_lenses[step_target].items():
            if self.v_from not in lenses:
                continue

            # Get node of field lens function
            lens_node = lenses[self.env.bases[self.v_from]].node
            # If the field in lhs appears in lens function then we conclude that
            # the original assignment will have side-effects in `field` when
            # crossing to version `step_target`.
            if (
                # TODO: type must match not just field name
                len(
                    fields_in_function(
                        lens_node,
                        {Field(name=lhs.attr, type=lhs.inferred_value)},
                    )
                )
                > 0
            ):
                # To reflect the side-effects of the assignment to `field`
                # (defined in version `self.v_from`) in version `step_target` we
                # use its corresponding put-lens. If none is defined, we can
                # infer one from its corresponding get-lens (`lens_node`). We
                # start by creating an `Attribute` of the form obj.lens, which
                # will be used to produce a `Call` node.
                put_lens_attr = get_obj_attribute(
                    obj=lhs.value,
                    attr=lens_node.name,
                    obj_type=lhs.value.inferred_value,
                    attr_type=lens_node.inferred_value,
                )
                # Then we add the right-hand side of assignment (`rhs`) as a
                # keyword argument.
                keywords = [keyword(arg=lhs.attr, value=rhs)]

                # All other field references (`ref`) in `lens_node` are added as
                # keyword arguments where the keyword is the field name and the
                # value is the object's current value (`obj.ref`)
                obj_type = annotation_from_type_value(lhs.value.inferred_value)
                references = fields_in_function(
                    lens_node, self.env.fields[obj_type][self.v_from]
                )
                for ref in references:
                    if ref.name != lhs.attr:
                        attr = get_obj_attribute(
                            obj=lhs.value,
                            attr=ref.name,
                            obj_type=lhs.value.inferred_value,
                            attr_type=ref.type,
                        )
                        keywords.append(keyword(arg=ref.name, value=attr))
                # Finally we create the call node in the form of
                # `obj.lens(field=rhs, f0=obj.f0,..,fn=obj.fn)`.
                self_call = Call(func=put_lens_attr, args=[], keywords=keywords)

                # Add put lens definition to class body if missing.
                if not self.env.put_lenses.has_lens(
                    v_from=self.v_from,
                    v_to=step_target,
                    field_name=field,
                ):
                    put_lens = PutLens(
                        fields=self.env.fields[obj_type][self.v_from]
                    ).visit(copy.deepcopy(lens_node))
                    self.env.put_lenses.put(
                        v_from=self.env.bases[self.v_from],
                        field_name=field,
                        v_to=self.env.bases[step_target],
                        lens=put_lens,
                    )
                    self.cls_ast.body.append(put_lens)

                # Assign the result of calling put lens to `field`.
                lens_target = get_obj_attribute(
                    obj=lhs.value,
                    attr=field,
                    ctx=ast.Store(),
                    obj_type=lhs.value.inferred_value,
                )
                lens_assign = Assign(targets=[lens_target], value=self_call)
                exprs.append(lens_assign)

            if step_target != self.v_target:
                # t = self.v_target
                # frm = self.v_from
                # self.v_target = step_target
                # rw_exprs = self.rw_assign(lhs, rhs)
                # self.v_from = step_target
                # self.v_target = t
                # exprs = []
                # for expr in rw_exprs:
                #     exprs.extend(self.visit(expr))
                # self.v_from = frm
                # self.v_target = t
                # return exprs

                exprs = self.step_rw_assign(lhs, rhs, step_target)

        return exprs

    def visit_AugAssign(self, node):
        """
        Implements a transformation for Augmented Assignment (+=, -=, *=, /=).

        If the target of the AugAssign has a reference to an object field, this method rewrites the
        AugAssign node by generating a regular assignment node and calling the `visit`
        method on that new node. Otherwise, the node remains
        unchanged.
        """
        ref_visitor = AssignLhsFieldCollector()
        ref_visitor.visit(node.target)
        if len(ref_visitor.references) == 0:
            return node
        else:
            left_node = copy.deepcopy(node.target)
            left_node.ctx = ast.Load()
            assign = Assign(
                targets=[node.target],
                value=BinOp(left=left_node, right=node.value, op=node.op),
            )
            return self.visit(assign)

    def visit_AnnAssign(self, node):
        """
        Implements a custom transformation for Annotation Assignment (e.g. self.x : int = 2).

        If the target of the AnnAssign has no object references, the node remains
        unchanged. If the target has a reference to an object field, this method
        generates a regular assignment node and calls the `visit` method on that new
        node if and only if the assignment has a value. Otherwise, the node is discarded.
        """
        ref_visitor = AssignLhsFieldCollector()
        ref_visitor.visit(node.target)
        if len(ref_visitor.references) == 0:
            return node
        if node.value:
            assign = Assign(
                targets=[node.target],
                value=node.value,
            )
            return self.visit(assign)
        return None

    def visit_Assign(self, node):
        exprs = []
        ref_visitor = AssignLhsFieldCollector()
        # We start by collecting all object field references in the left-hand side of the assignment
        for target in node.targets:
            ref_visitor.visit(target)
        # If the assignment affects at least one object field then we need to rewrite it.
        if ref_visitor.references:
            # When we rewrite an assignment, we introduce new expressions in the AST (namely, calling the appropriate lens function(s)).
            # Since the assignment value can produce side-effects (e.g. `obj.field = y = l.pop()`,
            # we can not copy this value and add it to the AST multiple times since this would not match the Python semantics.
            # As such, we need to introduce a new local variable holding the assignment value whenever
            # we have multiple targets, or a single tuple target.
            if len(node.targets) > 1 or isinstance(node.targets[0], Tuple):
                local_var = Name(id=fresh_var(), ctx=ast.Store())
                local_var.inferred_value = node.value.inferred_value
                local_assign = Assign(targets=[local_var], value=node.value)
                exprs.append(local_assign)
                node.value = local_var
            # TODO : Review this
            for target in node.targets:
                # We select all references that have this target as parent.
                references = [
                    ref.ref_node
                    for ref in ref_visitor.references
                    if ref.node == target
                ]
                # If the target has no field references, it remains intact.
                if len(references) == 0:
                    exprs.append(Assign(targets=[target], value=node.value))
                # If the target is an attribute we rewrite the assignment using lenses.
                elif isinstance(target, Attribute):
                    for ref in references:
                        exprs += self.__rw_assign(lhs=ref, rhs=node.value)

                # If the target is a subscript (e.g. obj.field[k] = v), then we extract the value to a local variable
                # and use it as the target.
                elif isinstance(target, Subscript):
                    for ref in references:
                        local_var = Name(id=fresh_var(), ctx=ast.Store())
                        local_var.inferred_value = ref.inferred_value
                        local_assign = Assign(targets=[local_var], value=ref)
                        exprs.append(local_assign)
                        node_copy = copy.copy(target)
                        node_copy.value = local_var
                        local_assign = Assign(
                            targets=[node_copy], value=node.value
                        )
                        exprs.append(local_assign)
                        exprs += self.__rw_assign(ref, local_var)
                elif isinstance(target, Tuple) or isinstance(target, List):
                    for index, el in enumerate(target.elts):
                        val = Subscript(
                            value=node.value, slice=ast.Constant(value=index)
                        )
                        val.inferred_value = el.inferred_value
                        if el in references:
                            el = self.__rw_assign(el, val)
                            exprs += el
                        else:
                            exprs.append(Assign(targets=[el], value=val))
                else:
                    node_copy = copy.copy(node)
                    node_copy.targets = [target]
                    exprs.append(node_copy)
        else:
            exprs.append(node)
        return exprs
