from copy import deepcopy
import inspect
import ast
from typing import Callable, Optional, Type
from lib_types import Graph, Version


def parse(obj):
    src = inspect.getsource(obj)
    return ast.parse(src)


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


def graph(cls_ast) -> Graph:
    return Graph({
        v.name: v
        for v in [Version(d.keywords) for d in cls_ast.decorator_list]
    })


def slice(cls, v):
    import lookup
    cls_ast = parse(cls).body[0]
    g = graph(cls_ast)
    cl_methods = lookup.method_all_lookup(cls_ast)
    sl_methods = {}
    for m in cl_methods:
        mdef = deepcopy(lookup.method_lookup(g, cls_ast, m, v))
        if mdef is not None:
            mver = [d for d in mdef.decorator_list
                    if d.func.id == 'at'][0].args[0].value
            lens_node, lens = lookup.lens_lookup(g, v, mver, cls)
            sl_methods[mdef.name] = lens_rw(mdef, lens)
            if lens is not None:
                sl_methods[lens_node.name] = remove_decorators(lens_node)
    cl = deepcopy(cls_ast)
    cl.name = cl.name + '_' + v
    cl.body = list(sl_methods.values())
    cl = remove_decorators(cl)
    return cl


def change_self_to_lens(node, lens):
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
    return node


def lens_rw(m: ast.FunctionDef, l: Optional[Callable]) -> ast.FunctionDef:
    rwm = remove_decorators(m)
    if l is None:
        return rwm
    return change_self_to_lens(rwm, l.__name__)


def rw(cls, v) -> Type:
    sl = slice(cls, v)
    s = ast.unparse(sl)
    out = [None]
    print(s)
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
