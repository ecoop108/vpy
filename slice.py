from copy import deepcopy
import inspect
import ast
from lib_types import Graph, Version


def graph(cls_ast) -> Graph:
    return Graph({
        v.name: v
        for v in [Version(d.keywords) for d in cls_ast.decorator_list]
    })


def slice(cls, v):
    import lookup
    src = inspect.getsource(cls)
    cls_ast = ast.parse(src).body[0]
    g = graph(cls_ast)
    cl_methods = set(
        [e.name for e in cls_ast.body if isinstance(e, ast.FunctionDef)])
    sl_methods = {}
    for m in cl_methods:
        mdef = deepcopy(lookup.method_lookup(g, cls_ast, m, v))
        if mdef is not None:
            mdef.decorator_list = []
            sl_methods[mdef.name] = mdef
    cl = deepcopy(cls_ast)
    cl.name = cl.name + '_' + v
    cl.body = list(sl_methods.values())
    cl.decorator_list = []
    return cl


def rw(cls, v):
    sl = slice(cls, v)
    s = ast.unparse(sl)
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
