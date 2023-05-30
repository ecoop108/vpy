import ast
from typing import Type
import inspect
from vpy.lib.adapt import tr_class
import importlib


def rw_module(mod, v):
    module_ast = ast.parse(inspect.getsource(mod))
    classes = [(node.name) for node in module_ast.body if isinstance(node, ast.ClassDef)]
    slices = []
    for cls_name in classes:
        cls = getattr(importlib.import_module(mod.__name__), cls_name)
        slices.append(ast.unparse(tr_class(mod, cls, v)))
    return slices


def rw(mod, cls: Type, v) -> Type:
    sl = tr_class(mod, cls, v)
    s = ast.unparse(sl)
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
