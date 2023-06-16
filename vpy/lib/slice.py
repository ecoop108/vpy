import ast
from types import ModuleType
from typing import Type
from vpy.lib.adapt import tr_class

from vpy.lib.lib_types import VersionId
from vpy.lib.utils import parse_class, parse_module


def rw_module(module: ModuleType, v: VersionId): # -> ModuleType
    module_ast = parse_module(module)
    classes = [(node) for node in module_ast.body
               if isinstance(node, ast.ClassDef)]
    slices = []
    for cls_ast in classes:
        slices.append(
            ast.unparse(ast.fix_missing_locations(tr_class(module, cls_ast,
                                                           v))))
    return slices


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    cls_ast, _ = parse_class(module, cls)
    sl = tr_class(module, cls_ast, v)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
