import ast
from ast import ClassDef, FunctionDef, Attribute
import copy
import inspect
from typing import Type, cast
from vpy.lib.utils import get_at, is_lens, remove_decorators, graph

import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Lens, VersionIdentifier


def tr_put_lens(node: ClassDef):

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
                    node.body.append(new_method)
            return node

        # def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
        #     return super().visit_FunctionDef(node)

        # def visit_Attribute(self, node: Attribute) -> Attribute:
        #     return super().visit_Attribute(node)

    node = PutLens().visit(node)
    return node


def tr_lens(parent, node, lenses: dict[str, Lens]):
    """
    Takes an AST node of a function and changes all expressions in the body of the form self.x
    to be of the form self.lens_x()
    """

    class LensTransformer(ast.NodeTransformer):

        def visit_Assign(self, node):
            if isinstance(
                    node.targets[0],
                    ast.Attribute) and node.targets[0].value.id == 'self':
                lens_node = lenses[node.targets[0].attr].put
                self_attr = ast.Attribute(value=ast.Name(id='self',
                                                         ctx=ast.Load()),
                                          attr=lens_node.name,
                                          ctx=ast.Load())
                self_call = ast.Call(func=self_attr,
                                     args=[node.value],
                                     keywords=[])
                if not any(e for e in parent.body if isinstance(
                        e, ast.FunctionDef) and e.name == lens_node.name):
                    parent.body.append(lens_node)
                return ast.Expr(value=self_call)
            return node

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if isinstance(node.ctx, ast.Load):
                    # Create the attribute node for "self.lens"
                    lens_node = lenses[node.attr].get
                    self_attr = ast.Attribute(value=ast.Name(id='self',
                                                             ctx=ast.Load()),
                                              attr=lens_node.name,
                                              ctx=ast.Load())

                    # Create the call node for "self.lens()"
                    self_call = ast.Call(func=self_attr, args=[], keywords=[])
                    node = self_call
                    if not any(e for e in parent.body if isinstance(
                            e, ast.FunctionDef) and e.name == lens_node.name):
                        parent.body.append(lens_node)
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
        parent = None

        def visit_ClassDef(self, node):
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
            lenses = lookup.lens_lookup(g, v, target, cls_ast)
            if lenses is not None:
                node = tr_lens(self.parent, node, lenses)
            return node

    cls_ast = tr_select_methods(g, cls_ast, v)
    cls_ast = tr_put_lens(cls_ast)
    ClassTransformer().visit(cls_ast)
    cls_ast.name += '_' + v
    if cls_ast.body == []:
        cls_ast.body.append(ast.Pass())

    return remove_decorators(cls_ast)
