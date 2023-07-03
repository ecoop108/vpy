from ast import Assign, Attribute, BinOp, Call, ClassDef, FunctionDef, Name, Subscript, arg, keyword
import copy

from vpy.lib.lib_types import FieldName, Graph, Lenses, VersionId
from vpy.lib.utils import FieldReferenceCollector, fresh_var, get_at, get_obj_attribute, get_self_obj, has_get_lens, is_field, is_obj_field
import ast


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
        if is_field(node, self.self_obj, self._fields) and isinstance(
                node.ctx, ast.Load):
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

    def rw_assign(self, target: Attribute,
                  value: ast.expr | None) -> list[ast.Expr]:
        exprs = []
        # iterate over lenses of class type(target.attr)
        for field in self.get_lenses[self.v_target]:
            lens_node = self.get_lenses[self.v_target][field][self.v_from]
            lens_ver = get_at(lens_node)
            if lens_ver != self.v_from:
                old_v_target = self.v_target
                self.v_target = lens_ver
                rw_exprs = self.rw_assign(target, value)
                self.v_target = old_v_target
                old_v_from = self.v_from
                self.v_from = lens_ver
                for expr in rw_exprs:
                    exprs.extend(self.visit(expr))
                self.v_from = old_v_from

            else:
                if value is not None and len(
                        fields_in_function(lens_node,
                                           {FieldName(target.attr)})) > 0:
                    # change field name to lens method call
                    #TODO: nested objects
                    self_attr = get_obj_attribute(obj=target.value.id,
                                                  attr=lens_node.name)
                    self_attr.value.inferred_value = target.value.inferred_value
                    # add value as argument
                    keywords = [keyword(arg=target.attr, value=value)]
                    # add fields referenced in lens as arguments
                    references = fields_in_function(lens_node,
                                                    self.fields[self.v_from])
                    for f in references:
                        if f != target.attr:
                            f_value = self.visit(ast.parse(f'self.{f}'))
                            keywords.append(keyword(arg=f, value=f_value))
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
                    lens_target = get_obj_attribute(obj=target.value.id,
                                                    attr=field,
                                                    ctx=ast.Store())
                    lens_target.value.inferred_value = target.value.inferred_value
                    lens_assign = Assign(targets=[lens_target],
                                         value=self_call)
                    ast.fix_missing_locations(lens_assign)
                    exprs.append(lens_assign)
        return exprs

    def visit_AugAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
                node.target, self.self_obj, self.fields[self.v_from]):
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
                node.target, self.self_obj, self.fields[self.v_from]):
            return self.rw_assign(node.target, node.value)
        return node

    def visit_Assign(self, node):
        exprs = []
        node.value = self.visit(node.value)
        # TODO: Does not work for nested obj attributes?
        target_references = set()
        for target in node.targets:
            visitor = FieldReferenceCollector(target.value.id,
                                              self.fields[self.v_from])
            visitor.visit(target)
            target_references = target_references.union(visitor.references)
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
                    and is_field(el, self.self_obj, self.fields[self.v_from])
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
            return node
        lens_node = self.get_lenses[self.v_from][node.attr][self.v_target]
        #TODO: Nested attributes
        self_attr = get_obj_attribute(obj=node.value.id, attr=lens_node.name)
        self_attr.value.inferred_value = node.value.inferred_value
        self_call = Call(func=self_attr, args=[], keywords=[])
        if not has_get_lens(self.cls_ast, lens_node):
            lens_node_copy = copy.deepcopy(lens_node)
            visitor = MethodRewriteTransformer(self.g, self.cls_ast,
                                               self.fields, self.get_lenses,
                                               self.v_target)
            lens_node_copy = visitor.visit(lens_node)
            self.cls_ast.body.append(lens_node_copy)
        return self_call
