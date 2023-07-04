from ast import Assign, Attribute, BinOp, Call, ClassDef, FunctionDef, Name, Subscript, arg, keyword
import copy

from vpy.lib.lib_types import FieldName, Graph, Lenses, VersionId
from vpy.lib.utils import FieldReferenceCollector, fresh_var, get_at, get_obj_attribute, get_self_obj, has_get_lens, is_field, is_obj_field
import ast


#TODO: What kind of fields? Only self?
def fields_in_function(node: FunctionDef, fields: set[FieldName]) -> set[str]:
    visitor = FieldReferenceCollector(get_self_obj(node), fields)
    visitor.visit(node)
    return visitor.references


class PutLens(ast.NodeTransformer):

    def __init__(self, fields: set[FieldName]):
        self._fields = fields

    def visit_FunctionDef(self, node):
        self.self_obj = get_self_obj(node)
        references = fields_in_function(node, self._fields)
        for f in references:
            node.args.kwonlyargs.append(arg(arg=f))
            node.args.kw_defaults.append(None)
        for dec in node.decorator_list:
            if isinstance(dec, Call) and isinstance(
                    dec.func, Name) and dec.func.id == 'get':
                dec.func.id = 'put'
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        if is_field(node, self._fields) and isinstance(node.ctx, ast.Load):
            node = Name(id=node.attr, ctx=ast.Load())
        else:
            node.value = self.visit(node.value)
        return node


class MethodRewriteTransformer(ast.NodeTransformer):

    def __init__(self, g: Graph, cls_ast: ClassDef,
                 fields: dict[VersionId, set[FieldName]], get_lenses: Lenses,
                 target: VersionId):
        self.g = g
        self.cls_ast = cls_ast
        self.fields = fields
        self.get_lenses = get_lenses
        self.v_target = target

    def visit_FunctionDef(self, node):
        v_from = get_at(node)
        if self.v_target == v_from:
            return node

        self_obj = node.args.args[0].arg
        lens_rw = LensTransformer(self.g, self.cls_ast, self.fields,
                                  self.get_lenses, self.v_target, v_from,
                                  self_obj)
        lens_rw.generic_visit(node)
        return node


class LensTransformer(ast.NodeTransformer):

    def __init__(self, g: Graph, cls_ast: ClassDef,
                 fields: dict[VersionId, set[FieldName]], get_lenses: Lenses,
                 v_target: VersionId, v_from: VersionId, self_obj: str):
        self.g = g
        self.cls_ast = cls_ast
        self.fields = fields
        self.get_lenses = get_lenses
        self.v_target = v_target
        self.v_from = v_from
        self.put_lenses = {}
        self.self_obj = self_obj

    def step_rw_assign(self, target: Attribute, value: ast.expr | None,
                       lens_ver) -> list[ast.Expr]:
        exprs = []
        old_v_target = self.v_target
        self.v_target = lens_ver
        rw_exprs = self.rw_assign(target, value)
        self.v_target = old_v_target
        old_v_from = self.v_from
        self.v_from = lens_ver
        for expr in rw_exprs:
            exprs.extend(self.visit(expr))
        self.v_from = old_v_from
        return exprs

    def rw_assign(self, target: Attribute,
                  value: ast.expr | None) -> list[ast.Expr]:
        #TODO: iterate over lenses of class type(target.attr)
        for field in self.get_lenses[self.v_target]:
            lens_node = self.get_lenses[self.v_target][field][self.v_from]
            lens_ver = get_at(lens_node)
            if lens_ver != self.v_from:
                return self.step_rw_assign(target, value, lens_ver)
            else:
                exprs = []
                if value is not None and len(
                        fields_in_function(lens_node,
                                           {FieldName(target.attr)})) > 0:
                    # change field name to lens method call
                    self_attr = get_obj_attribute(
                        obj=target.value,
                        attr=lens_node.name,
                        obj_type=target.value.inferred_value)
                    # add value as argument
                    keywords = [keyword(arg=target.attr, value=value)]
                    # Add fields referenced in lens as arguments
                    references = fields_in_function(lens_node,
                                                    self.fields[self.v_from])
                    for ref in references:
                        if ref != target.attr:
                            attr = get_obj_attribute(
                                obj=target.value,
                                attr=ref,
                                obj_type=target.value.inferred_value)
                            attr = self.visit(attr)
                            keywords.append(keyword(arg=ref, value=attr))

                    self_call = Call(func=self_attr,
                                     args=[],
                                     keywords=keywords)

                    # add put lens definition if missing
                    if (self.v_from, self.v_target) not in self.put_lenses:
                        put_lens = PutLens(self.fields[self.v_from]).visit(
                            copy.deepcopy(lens_node))
                        self.put_lenses[(self.v_from,
                                         self.v_target)] = put_lens
                        self.cls_ast.body.append(put_lens)

                    # Rewrite assignment using put lens
                    lens_target = get_obj_attribute(
                        obj=target.value,
                        attr=field,
                        ctx=ast.Store(),
                        obj_type=target.value.inferred_value)
                    lens_assign = Assign(targets=[lens_target],
                                         value=self_call)
                    ast.fix_missing_locations(lens_assign)
                    exprs.append(lens_assign)
                    return exprs
        return []

    def visit_AugAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
                node.target, self.fields[self.v_from]):
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
                node.target, self.fields[self.v_from]):
            return self.rw_assign(node.target, node.value)
        return node

    def visit_Assign(self, node):
        exprs = []
        # Rewrite right-hand side of assignment.
        node.value = self.visit(node.value)
        # Collect all field references in left-hand side of assignment.
        target_references = set()
        for target in node.targets:
            if isinstance(target, Attribute):
                #TODO: Fix this None?
                visitor = FieldReferenceCollector(None,
                                                  self.fields[self.v_from])
                visitor.visit(target)
                target_references = target_references.union(visitor.references)
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
            if isinstance(target, Attribute) and is_obj_field(
                    target, {self.cls_ast.name: self.fields[self.v_from]}):
                exprs += self.rw_assign(target, node.value)
            elif isinstance(target, Name):
                node_copy = copy.deepcopy(node)
                node_copy.targets = [target]
                exprs.append(node_copy)
            elif isinstance(target, ast.Tuple):
                fields = [
                    el for el in target.elts if isinstance(el, Attribute)
                    and is_field(el, self.fields[self.v_from])
                ]
                if len(fields) == 0:
                    exprs.append(node)
                else:
                    local_tuple_var = Name(id=fresh_var(), ctx=ast.Store())
                    local_tuple_assign = Assign(targets=[local_tuple_var],
                                                value=node.value)
                    #TODO: check if this makes sense
                    # local_tuple_var.inferred_value = node.value.inferred_value
                    exprs.append(local_tuple_assign)
                    for index, el in enumerate(target.elts):
                        val = Subscript(value=local_tuple_var,
                                        slice=ast.Constant(value=index))
                        if el in fields:
                            el = self.rw_assign(el, val)
                            exprs += el
                        else:
                            exprs.append(Assign(targets=[el], value=val))
            elif isinstance(target, ast.List):
                assert (False)
        return exprs

    def visit_Attribute(self, node):
        if not (is_obj_field(node,
                             {self.cls_ast.name: self.fields[self.v_from]})
                and isinstance(node.ctx, ast.Load)):
            node = self.generic_visit(node)
            return node
        #TODO: Nested attributes, lenses
        lens_node = self.get_lenses[self.v_from][node.attr][self.v_target]
        self_attr = get_obj_attribute(obj=node.value,
                                      attr=lens_node.name,
                                      obj_type=node.value.inferred_value)
        self_call = Call(func=self_attr, args=[], keywords=[])
        if not has_get_lens(self.cls_ast, lens_node):
            lens_node_copy = copy.deepcopy(lens_node)
            visitor = MethodRewriteTransformer(self.g, self.cls_ast,
                                               self.fields, self.get_lenses,
                                               self.v_target)
            lens_node_copy = visitor.visit(lens_node)
            self.cls_ast.body.append(lens_node_copy)
        return self_call

    def visit_Call(self, node: Call):
        for index, arg in enumerate(node.args):
            node.args[index] = self.visit(arg)
        for index, kw in enumerate(node.keywords):
            node.keywords[index].value = self.visit(kw.value)
        return node
