import ast
from ast import Attribute, ClassDef, FunctionDef, Name, arg, keyword
import copy
from typing import Type

from vpy.lib.utils import get_at, has_put_lens, is_lens, is_self_attribute, parse_class, remove_decorators
import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Graph, VersionIdentifier


def tr_put_lens(node: FunctionDef, fields):
    """Takes an AST node of a get lens and returns a put lens by replacing all
    fields of the form self.x with x and adding x as an argument to the lens.
    """

    class FieldCollector(ast.NodeVisitor):

        def __init__(self, fields):
            self.fields = fields
            self.references = set()

        def visit_Attribute(self, node):
            if is_self_attribute(node) and node.attr in self.fields:
                self.references.add(node.attr)
            self.visit(node.value)

    class PutLens(ast.NodeTransformer):

        def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
            visitor = FieldCollector(fields)
            visitor.visit(node)
            for f in visitor.references:
                node.args.kwonlyargs.append(arg(arg=f))
                node.args.kw_defaults.append(None)
            for expr in node.body:
                self.visit(expr)
            return node

        def visit_Attribute(self, node) -> Attribute | Name:
            if is_self_attribute(node) and node.attr in fields:
                if isinstance(node.ctx, ast.Load):
                    node = Name(id=node.attr, ctx=ast.Load())
            else:
                node.value = self.visit(node.value)
            return node

    new_method = copy.deepcopy(node)
    new_method.name = node.name
    for dec in new_method.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(
                dec.func, ast.Name) and dec.func.id == 'get':
            dec.func.id = 'put'
    new_method = PutLens().visit(new_method)
    return new_method


def tr_lens(cls_node: ClassDef, tr_cls_node: ClassDef, node: FunctionDef,
            g: Graph, v: VersionIdentifier, t: VersionIdentifier):
    """
    Takes an AST node of a function and changes all expressions in the body of the form self.x
    to be of the form self.lens_x()
    """

    def check_field_in_function(node, field):
        for child_node in ast.walk(node):
            #TODO: Get fields from other functions
            if isinstance(child_node, ast.Call):
                pass
            if isinstance(child_node, ast.Attribute):
                if is_self_attribute(child_node) and child_node.attr == field:
                    return True
        return False

    class LensTransformer(ast.NodeTransformer):

        def rw_lens(self, target: ast.Attribute,
                    value: ast.expr | None) -> list[ast.Expr]:
            exprs = []
            if lenses_t_v is not None:
                for field in lenses_t_v:
                    if check_field_in_function(lenses_t_v[field], target.attr):
                        lens_node = lenses_t_v[field]
                        self_attr = ast.Attribute(value=ast.Name(
                            id='self', ctx=ast.Load()),
                                                  attr=lens_node.name,
                                                  ctx=ast.Load())
                        if value:
                            rw_value = self.visit(value)
                            self_call = ast.Call(
                                func=self_attr,
                                args=[],
                                keywords=[
                                    keyword(arg=target.attr, value=rw_value)
                                ] + [
                                    keyword(arg=f,
                                            value=self.visit(
                                                ast.parse(f'self.{f}')))
                                    for f in fields_t if f != target.attr
                                    # TODO: only add fields that appear in lens body
                                ])

                            if not has_put_lens(tr_cls_node, lens_node):
                                put_lens = tr_put_lens(lens_node, fields_t)
                                tr_cls_node.body.append(put_lens)
                                tr_cls_node.body.remove(lens_node)
                            lens_target = Attribute(value=ast.Name(
                                id='self', ctx=ast.Store()),
                                                    attr=field)
                            lens_assign = ast.Assign(targets=[lens_target],
                                                     value=self_call)
                            exprs.append(lens_assign)
            return [ast.Expr(value=e) for e in exprs]

        def visit_AugAssign(self, node: ast.AugAssign):
            if isinstance(node.target, ast.Attribute) and is_self_attribute(
                    node.target) and node.target.attr in fields_t:
                left_node = copy.deepcopy(node.target)
                left_node.ctx = ast.Load()
                unfold = ast.BinOp(left=left_node,
                                   right=node.value,
                                   op=node.op)
                assign = ast.Assign(targets=[node.target], value=unfold)
                return self.rw_lens(node.target, assign.value)
            if node.value:
                node.value = self.visit(node.value)
            return node

        def visit_AnnAssign(self, node: ast.AnnAssign):
            if isinstance(node.target, ast.Attribute) and is_self_attribute(
                    node.target) and node.target.attr in fields_t:
                return self.rw_lens(node.target, node.value)
            if node.value:
                node.value = self.visit(node.value)
            return node

        def visit_Assign(self, node):
            exprs = []
            # rewrite left-hand side of assignment
            node.value = self.visit(node.value)
            for target in node.targets:
                if isinstance(target, ast.Attribute) and is_self_attribute(
                        target) and target.attr in fields_t:
                    exprs += self.rw_lens(target, node.value)
                elif isinstance(target, ast.Name):
                    node_copy = copy.deepcopy(node)
                    node_copy.targets = [target]
                    exprs.append(node_copy)
                elif isinstance(target, ast.Tuple):
                    assert (False)
                elif isinstance(target, ast.List):
                    assert (False)
            return exprs

        def visit_Attribute(self, node):
            if is_self_attribute(node) and node.attr in fields_t:
                if isinstance(node.ctx, ast.Load):
                    if lenses_v_t is not None:
                        if node.attr in lenses_v_t:
                            lens_node = lenses_v_t[node.attr]
                            self_attr = ast.Attribute(value=ast.Name(
                                id='self', ctx=ast.Load()),
                                                      attr=lens_node.name,
                                                      ctx=ast.Load())

                            # Create the call node for "self.lens()"
                            self_call = ast.Call(func=self_attr,
                                                 args=[],
                                                 keywords=[])
                            return self_call
                        else:
                            raise Exception(
                                f'Missing lens for field {node.attr} from version {v} to version {t}'
                            )
            return node

    lenses_t_v = lookup.lens_at(g, t, v, tr_cls_node)
    lenses_v_t = lookup.lens_at(g, v, t, cls_node)
    fields_t = lookup.fields_at(g, cls_node, t)
    LensTransformer().visit(node)
    return node


def tr_select_methods(g: Graph, node: ClassDef,
                      v: VersionIdentifier) -> ClassDef:

    class TransformerSelectMethods(ast.NodeTransformer):

        def visit_ClassDef(self, node: ClassDef) -> ClassDef:
            for expr in list(node.body):
                if not isinstance(expr, FunctionDef):
                    continue
                if is_lens(expr):
                    # node.body.remove(expr)
                    continue
                mdef = lookup.method_lookup(g, node, expr.name, v)
                if mdef is None or get_at(mdef) != get_at(expr):
                    node.body.remove(expr)
                #     continue
                # target = get_at(mdef)
                # mver = get_at(expr)
                # if mver != target:
                #     node.body.remove(expr)
            return node

    node = TransformerSelectMethods().visit(node)
    return node


def tr_class(mod, cls: Type, v: VersionIdentifier) -> ClassDef:
    cls_ast, g = parse_class(cls)
    tr_cls_ast = copy.deepcopy(cls_ast)

    class ClassTransformer(ast.NodeTransformer):
        """
        Takes an AST node of a class and selects only methods for version `v`.
        Each method is rewritten to match the context of `v` if needed.
        """
        parent = tr_cls_ast

        def visit_ClassDef(self, node: ClassDef):
            self.parent = node
            for expr in list(node.body):
                expr = self.visit(expr)
            return node

        def visit_FunctionDef(self, node):
            if is_lens(node):
                return node
            mdef = lookup.method_lookup(g, cls_ast, node.name, v)
            if mdef is None:
                assert (False)
            target = get_at(mdef)
            lenses = lookup.lens_at(g, target, v, cls_ast)
            if lenses is not None:
                node = tr_lens(cls_ast, self.parent, node, g, v, target)
            return node

    tr_cls_ast = tr_select_methods(g, tr_cls_ast, v)
    # tr_cls_ast = tr_put_lens(tr_cls_ast)
    ClassTransformer().visit(tr_cls_ast)
    tr_cls_ast.name += '_' + v
    if tr_cls_ast.body == []:
        tr_cls_ast.body.append(ast.Pass())
    return remove_decorators(tr_cls_ast)
