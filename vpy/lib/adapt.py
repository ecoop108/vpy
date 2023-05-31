import ast
from ast import Attribute, ClassDef, FunctionDef, Name, arg, keyword
import copy
import inspect
from typing import Type, cast
from vpy.lib.utils import get_at, is_lens, remove_decorators, graph

import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Graph, Lens, VersionIdentifier


def tr_put_lens(node: ClassDef):

    class FieldCollector(ast.NodeVisitor):

        def __init__(self):
            self.fields = set()

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if isinstance(node.ctx, ast.Load):
                    self.fields.add(node.attr)

    class PutLens(ast.NodeTransformer):

        def visit_ClassDef(self, node: ClassDef) -> ClassDef:
            for body_item in list(node.body):
                if isinstance(body_item,
                              ast.FunctionDef) and is_lens(body_item):
                    # Create a new method with the modified name
                    new_method = copy.deepcopy(body_item)
                    new_method.name = body_item.name
                    # Modify the @get decorator
                    for dec in new_method.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(
                                dec.func, ast.Name) and dec.func.id == 'get':
                            dec.func.id = 'put'
                    # Add the new method to the class body
                    self.visit(new_method)
                    node.body.append(new_method)
            return node

        def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
            field_col = FieldCollector()
            field_col.visit(node)
            for f in field_col.fields:
                node.args.kwonlyargs.append(arg(arg=f))
                node.args.kw_defaults.append(None)
            for expr in node.body:
                self.visit(expr)
            return node

        def visit_Attribute(self, node) -> Attribute | Name:
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if isinstance(node.ctx, ast.Load):
                    node = Name(id=node.attr, ctx=ast.Load())
            else:
                node.value = self.visit(node.value)
            return node

    node = PutLens().visit(node)
    return node


def tr_lens(cls_node: ClassDef, node: FunctionDef, g: Graph,
            v: VersionIdentifier, t: VersionIdentifier):
    """
    Takes an AST node of a function and changes all expressions in the body of the form self.x
    to be of the form self.lens_x()
    """

    def check_field_in_function(node, field):
        # Traverse the AST of the function definition
        for child_node in ast.walk(node):
            if isinstance(child_node, ast.Attribute):
                if isinstance(child_node.value,
                              ast.Name) and child_node.value.id == 'self':
                    if child_node.attr == field:
                        return True
        return False

    class LensTransformer(ast.NodeTransformer):

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target,
                              ast.Attribute) and target.value.id == 'self':
                    lenses = lookup.lens_lookup(g, t, v, cls_node)
                    exprs = []
                    #TODO: fix field lookup
                    t_fields = lookup.fields_lookup(g, cls_node, t)
                    for field in lenses:
                        if check_field_in_function(lenses[field].get,
                                                   target.attr):
                            lens_node = lenses[field].put
                            self_attr = ast.Attribute(value=ast.Name(
                                id='self', ctx=ast.Load()),
                                                      attr=lens_node.name,
                                                      ctx=ast.Load())
                            rw_value = self.visit(node.value)
                            self_call = ast.Call(
                                func=self_attr,
                                args=[],
                                keywords=[
                                    keyword(arg=target.attr, value=rw_value)
                                ] + [
                                    keyword(arg=f,
                                            value=ast.parse(f'self.{f}'))
                                    for f in t_fields if f != target.attr
                                ])
                            if not any(e for e in cls_node.body
                                       if isinstance(e, ast.FunctionDef)
                                       and e.name == lens_node.name):
                                cls_node.body.append(lens_node)
                            exprs.append(self_call)
                    return [ast.Expr(value=self_call)]
            return node

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if isinstance(node.ctx, ast.Load):
                    # Create the attribute node for "self.lens"
                    lenses = lookup.lens_lookup(g, v, t, cls_node)
                    lens_node = lenses[node.attr].get
                    self_attr = ast.Attribute(value=ast.Name(id='self',
                                                             ctx=ast.Load()),
                                              attr=lens_node.name,
                                              ctx=ast.Load())

                    # Create the call node for "self.lens()"
                    self_call = ast.Call(func=self_attr, args=[], keywords=[])
                    node = self_call
                    if not any(e for e in cls_node.body if isinstance(
                            e, ast.FunctionDef) and e.name == lens_node.name):
                        cls_node.body.append(lens_node)
            return node

    LensTransformer().visit(node)
    return node


def tr_select_methods(g, node, v) -> ClassDef:

    class TransformerSelectMethods(ast.NodeTransformer):

        def visit_ClassDef(self, node: ClassDef) -> ClassDef:
            for expr in list(node.body):
                if not isinstance(expr, FunctionDef):
                    continue
                if is_lens(expr):
                    # node.body.remove(expr)
                    continue
                mdef = lookup.method_lookup(g, node, expr.name, v)
                if mdef is None:
                    node.body.remove(expr)
                    continue
                target = get_at(mdef)
                mver = get_at(expr)
                if mver != target:
                    node.body.remove(expr)
            return node

    node = TransformerSelectMethods().visit(node)
    return node


def tr_class(mod, cls: Type, v: VersionIdentifier) -> ClassDef:
    src = inspect.getsource(cls)
    cls_ast: ast.ClassDef = cast(ClassDef, ast.parse(src).body[0])
    g = graph(cls_ast)

    class ClassTransformer(ast.NodeTransformer):
        """
        Takes an AST node of a class and selects only methods for version `v`.
        Each method is rewritten to match the context of `v` if needed.
        """
        parent = cls_ast

        def visit_ClassDef(self, node: ClassDef):
            self.parent = node
            for expr in list(node.body):
                if is_lens(expr):
                    continue
                expr = self.visit(expr)
            return node

        def visit_FunctionDef(self, node):
            mdef = lookup.method_lookup(g, cls_ast, node.name, v)
            target = get_at(mdef)
            # fields = lookup.fields_lookup(g, cls_ast, target)
            lenses = lookup.lens_lookup(g, target, v, cls_ast)
            if lenses is not None:
                node = tr_lens(self.parent, node, g, v, target)
            return node

    cls_ast = tr_select_methods(g, cls_ast, v)
    cls_ast = tr_put_lens(cls_ast)
    ClassTransformer().visit(cls_ast)
    cls_ast.name += '_' + v
    if cls_ast.body == []:
        cls_ast.body.append(ast.Pass())

    return remove_decorators(cls_ast)
