from ast import ClassDef
from vpy.lib.transformers.module import ModuleTransformer

from vpy.lib.lib_types import VersionId
from vpy.typechecker.checker import check_cls


def tr_class(mod, cls_ast: ClassDef, v: VersionId) -> ClassDef:
    status, err = check_cls(mod, cls_ast)
    if not status:
        raise Exception(err)
    module = ModuleTransformer(v).visit(cls_ast)
    return module
