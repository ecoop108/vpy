import ast
from types import ModuleType
from typing import Type
from vpy.lib.adapt import tr_class

from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.module import ModuleTransformer
from vpy.lib.utils import parse_class, parse_module
from vpy.typechecker.checker import check_cls


def rw_module(module: ModuleType, v: VersionId):  # -> ModuleType
    mod_ast = ModuleTransformer(v).visit(parse_module(module))
    return [ast.unparse(ast.fix_missing_locations(mod_ast))]


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    cls_ast, _ = parse_class(module, cls)
    status, err = check_cls(module, cls_ast)
    if not status:
        raise Exception(err)
    sl = ModuleTransformer(v).visit(cls_ast)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [type]
    exec(s + f"\nout[0]={cls.__name__}_{v}")
    return out[0]
