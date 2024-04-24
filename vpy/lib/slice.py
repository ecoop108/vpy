import ast
from types import ModuleType
from typing import Type, TypeVar


from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.module import ModuleTransformer
from vpy.lib.utils import parse_module

T = TypeVar("T")


def eval_slice(module: ModuleType, cls: Type[T], v: VersionId) -> Type[T]:
    mod_ast, _ = parse_module(module.__file__)
    sl_mod = ModuleTransformer(v).visit(mod_ast)
    try:
        sl_cls = next(
            c
            for c in sl_mod.body
            if isinstance(c, ast.ClassDef) and c.name == f"{cls.__name__}"
        )
    except StopIteration:
        assert False
    s = ast.unparse(ast.fix_missing_locations(sl_cls))
    out: list[Type[T]] = [cls]
    exec(s + f"\nout[0]={cls.__name__}")
    return out[0]
