import ast
from collections import defaultdict
from types import ModuleType
from typing import Type

from vpy.lib import lookup

from vpy.lib.lib_types import Environment, VersionId
from vpy.lib.transformers.cls import ClassTransformer
from vpy.lib.utils import parse_class, get_module_environment, parse_module
from vpy.typechecker.checker import check_cls


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    mod_ast = parse_module(module)
    mod_env = get_module_environment(mod_ast)

    cls_ast, g = parse_class(module, cls)

    status, err = check_cls(module, cls_ast, mod_env)
    if not status:
        raise Exception(err)
    sl = ClassTransformer(v=v, env=mod_env).visit(cls_ast)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [type]
    exec(s + f"\nout[0]={cls.__name__}_{v}")
    return out[0]
