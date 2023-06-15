import ast
from typing import Type
from vpy.lib.adapt import tr_class
import importlib

from vpy.lib.lib_types import VersionId
from vpy.lib.utils import parse_module


def rw_module(mod, v: VersionId):
    module_ast = parse_module(mod)
    classes = [(node.name) for node in module_ast.body
               if isinstance(node, ast.ClassDef)]
    slices = []
    for cls_name in classes:
        cls = getattr(importlib.import_module(mod.__name__), cls_name)
        slices.append(
            ast.unparse(ast.fix_missing_locations(tr_class(mod, cls, v))))
    return slices


def eval_slice(mod, cls: Type, v: VersionId) -> Type:
    sl = tr_class(mod, cls, v)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
