import ast
from ast import ClassDef
import inspect
from typing import Type, cast
from vpy.lib.utils import get_at, is_lens, remove_decorators, graph

import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Lens, VersionIdentifier


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


def tr_class(mod, cls: Type, v: VersionIdentifier) -> ClassDef:
    src = inspect.getsource(cls)
    cls_ast: ast.ClassDef = cast(ClassDef, ast.parse(src).body[0])
    cls_ast_orig = cast(ClassDef, ast.parse(src).body[0])
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
                    node.body.remove(expr)
                    continue
                new = self.visit(expr)
                if new is None:
                    node.body.remove(expr)
                else:
                    expr = new
            return node

        def visit_FunctionDef(self, node):
            mdef = lookup.method_lookup(g, cls_ast, node.name, v)
            if mdef is None:
                return None
            target = get_at(mdef)
            mver = get_at(node)
            if mver != target:
                return None
            fields = lookup.fields_lookup(g, cls_ast, target)
            lenses = lookup.lens_lookup(g, v, target, cls_ast_orig)
            if lenses is not None:
                node = tr_lens(self.parent, node, lenses)
            return node

    ClassTransformer().visit(cls_ast)
    cls_ast.name += '_' + v
    if cls_ast.body == []:
        cls_ast.body.append(ast.Pass())

    return remove_decorators(cls_ast)
