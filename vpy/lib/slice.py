import ast
from types import ModuleType
from typing import Type


from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.module import ModuleTransformer
from vpy.lib.utils import parse_module


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    mod_ast, _ = parse_module(module)
    sl_mod = ModuleTransformer(v).visit(mod_ast)

    sl_cls = [
        c
        for c in sl_mod.body
        if isinstance(c, ast.ClassDef) and c.name == f"{cls.__name__}_{v}"
    ][0]

    s = ast.unparse(ast.fix_missing_locations(sl_cls))
    out = [type]
    exec(s + f"\nout[0]={cls.__name__}_{v}")
    return out[0]
