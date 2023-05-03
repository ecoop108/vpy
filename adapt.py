import ast
import inspect
from typing import Type
from aux import get_at

import lookup
from lib_types import Graph, Version


def graph(cls_ast: ast.ClassDef) -> Graph:
    return Graph({
        v.name: v
        for v in [Version(d.keywords) for d in cls_ast.decorator_list]
    })


def remove_decorators(node):
    exclude = ['at', 'version', 'lens']
    new_decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Name) and decorator.func.id in exclude:
            pass
        else:
            new_decorators.append(decorator)
    node.decorator_list = new_decorators
    return node


def tr_lens(node, lens):
    """
    Takes an AST node of a function and changes all expressions in the body of the form self.x
    to be of the form self.lens_x()
    """

    class LensTransformer(ast.NodeTransformer):

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':

                if isinstance(node.ctx, ast.Load):
                    # Create the attribute node for "self.lens"
                    self_attr = ast.Attribute(value=ast.Name(id='self',
                                                             ctx=ast.Load()),
                                              attr=lens,
                                              ctx=ast.Load())

                    # Create the call node for "self.lens()"
                    self_call = ast.Call(func=self_attr, args=[], keywords=[])
                    node = self_call
            return node

    LensTransformer().visit(node)
    return remove_decorators(node)


def tr_class(cls: Type, v: str):
    src = inspect.getsource(cls)
    cls_ast: ast.ClassDef = ast.parse(src).body[0]
    g = graph(cls_ast)

    class ClassTransformer(ast.NodeTransformer):
        parent = None

        def visit_ClassDef(self, node):
            self.parent = node
            for idx,expr in enumerate(list(node.body)):
                new =self.visit(expr)
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
            lens_node, lens = lookup.lens_lookup(g, v, mver, cls)
            if lens is not None:
                node = tr_lens(node, lens_node.name)
                self.parent.body.append(remove_decorators(lens_node))
            return remove_decorators(node)

    ClassTransformer().visit(cls_ast)
    cls_ast.name += '_' + v
    return remove_decorators(cls_ast)
