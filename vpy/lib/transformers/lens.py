from ast import Attribute, ClassDef, FunctionDef, Name, arg, keyword, AnnAssign, Assign, BinOp, Call, AugAssign, Subscript
import copy
from vpy.lib.lib_types import Graph, Lenses, VersionId
from vpy.lib.lookup import path_lookup
from vpy.lib.utils import fresh_var, get_at, get_self_obj, has_get_lens, is_field, obj_attribute
import ast


class FieldCollector(ast.NodeVisitor):

    def __init__(self, self_obj: str, fields: set[str]):
        self.fields = fields
        self.self_obj = self_obj
        self.references: set[str] = set()

    def visit_Attribute(self, node):
        if is_field(node, self.self_obj, self.fields):
            self.references.add(node.attr)
        self.visit(node.value)


def fields_in_function(node: FunctionDef, fields: set[str]) -> set[str]:
    visitor = FieldCollector(get_self_obj(node), fields)
    visitor.visit(node)
    return visitor.references


class PutLens(ast.NodeTransformer):

    def __init__(self, fields: set[str]):
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


class LensTransformer(ast.NodeTransformer):

    def __init__(self, g: Graph, cls_ast: ClassDef, bases: dict[VersionId,
                                                                VersionId],
                 fields: dict[VersionId, set[str]], get_lenses: Lenses,
                 target: VersionId):
        self.g = g
        self.cls_ast = cls_ast
        self.bases = bases
        self.fields = fields
        self.get_lenses = get_lenses
        self.target = target
        self.put_lenses = {}

    def visit_FunctionDef(self, node):
        self.v = get_at(node)
        self.self_obj = node.args.args[0].arg
        if self.bases[self.target] == self.bases[self.v]:
            return node
        path = path_lookup(self.g, self.v, self.target, self.get_lenses)
        if path is not None:
            for v, t in path:
                self.v, self.target = v, t
                self.generic_visit(node)
        return node

    def rw_assign(self, target: Attribute,
                  value: ast.expr | None) -> list[ast.Expr]:
        exprs = []
        for field, lens_node in self.get_lenses[self.v][self.target].items():

            if len(fields_in_function(
                    lens_node, {target.attr})) > 0 and value is not None:
                # change field name to lens method call
                self_attr = obj_attribute(obj=self.self_obj,
                                          attr=lens_node.name)
                # add value as argument
                keywords = [keyword(arg=target.attr, value=value)]
                # add fields referenced in lens as arguments
                references = fields_in_function(lens_node,
                                                self.fields[self.v])
                for f in references:
                    if f != target.attr:
                        f_value = self.visit(ast.parse(f'self.{f}'))
                        keywords.append(keyword(arg=f, value=f_value))
                self_call = Call(func=self_attr, args=[], keywords=keywords)
                # add put lens definition if missing
                if (self.v, self.target) not in self.put_lenses:
                    put_lens = PutLens(self.fields[self.v]).visit(
                        copy.deepcopy(lens_node))
                    self.put_lenses[(self.v, self.target)] = put_lens
                    self.cls_ast.body.append(put_lens)
                lens_target = obj_attribute(obj=self.self_obj,
                                            attr=field,
                                            ctx=ast.Store())
                lens_assign = Assign(targets=[lens_target], value=self_call)
                exprs.append(lens_assign)
        return exprs

    def visit_AugAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
                node.target, self.self_obj, self.fields[self.v]):
            left_node = copy.deepcopy(node.target)
            left_node.ctx = ast.Load()
            unfold = BinOp(left=left_node, right=node.value, op=node.op)
            unfold = self.visit(unfold)
            assign = Assign(targets=[node.target], value=unfold)
            return self.rw_assign(node.target, assign.value)
        return node

    def visit_AnnAssign(self, node):
        if node.value:
            node.value = self.visit(node.value)
        if isinstance(node.target, Attribute) and is_field(
                node.target, self.self_obj, self.fields[self.v]):
            return self.rw_assign(node.target, node.value)
        return node

    def visit_Assign(self, node):
        exprs = []
        node.value = self.visit(node.value)
        visitor = FieldCollector(self.self_obj, self.fields[self.v])
        for target in node.targets:
            visitor.visit(target)

        if len(visitor.references) > 0:
            local_var = Name(id=fresh_var(), ctx=ast.Store())
            local_assign = Assign(targets=[local_var], value=node.value)
            exprs.append(local_assign)
            node.value = local_var

        for target in node.targets:
            if isinstance(target, Attribute) and is_field(
                    target, self.self_obj, self.fields[self.v]):
                exprs += self.rw_assign(target, node.value)
            elif isinstance(target, Name):
                node_copy = copy.deepcopy(node)
                node_copy.targets = [target]
                exprs.append(node_copy)
            elif isinstance(target, ast.Tuple):
                fields = [
                    el for el in target.elts if isinstance(el, Attribute)
                    and is_field(el, self.self_obj, self.fields[self.v])
                ]
                if len(fields) == 0:
                    exprs.append(node)
                else:
                    local_tuple_var = Name(id=fresh_var(), ctx=ast.Store())
                    local_tuple_assign = Assign(targets=[local_tuple_var],
                                                value=node.value)
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
        if not (is_field(node, self.self_obj, self.fields[self.v])
                and isinstance(node.ctx, ast.Load)):
            return node
        lenses_t_v = self.get_lenses[self.bases[self.target]][self.bases[
            self.v]]
        if node.attr not in lenses_t_v:
            return node
        lens_node = lenses_t_v[node.attr]
        self_attr = obj_attribute(obj=self.self_obj, attr=lens_node.name)
        self_call = Call(func=self_attr, args=[], keywords=[])
        if not has_get_lens(self.cls_ast, lens_node):
            lens_node = copy.deepcopy(lens_node)
            visitor = copy.deepcopy(self)
            lens_node = visitor.visit(lens_node)
            self.cls_ast.body.append(lens_node)
        return self_call
