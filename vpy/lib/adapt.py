import ast
from ast import ClassDef, FunctionDef
import copy
from typing import Type
from vpy.lib.transformers.method_selection import SelectMethodsTransformer

from vpy.lib.utils import get_at, is_lens, parse_class, remove_decorators
import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Graph, VersionIdentifier
from vpy.lib.transformers.lens import LensTransformer


def tr_class(mod, cls: Type, v: VersionIdentifier) -> ClassDef:
    cls_ast, g = parse_class(cls)
    tr_cls_ast = copy.deepcopy(cls_ast)

    bases = {}
    fields = {}
    lenses = {}
    for k in g.keys():
        base = lookup.base(g, cls_ast, k)
        if base is not None:
            bases[k], fields[k] = base
    for k in g.keys():
        for t in g.keys():
            if k != t:
                if bases[k] not in lenses:
                    lenses[bases[k]] = {}
                lenses[bases[k]][bases[t]] = lookup.lens_at(
                    g, k, t, tr_cls_ast)
    tr_cls_ast = SelectMethodsTransformer(g=g, v=v).visit(tr_cls_ast)
    tr_cls_ast = LensTransformer(cls_ast=tr_cls_ast,
                                 bases=bases,
                                 fields=fields,
                                 lenses=lenses,
                                 v=v).visit(tr_cls_ast)
    tr_cls_ast.name += '_' + v
    if tr_cls_ast.body == []:
        tr_cls_ast.body.append(ast.Pass())
    return remove_decorators(tr_cls_ast)
