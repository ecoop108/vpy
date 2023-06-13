import ast
from ast import ClassDef
import copy
from typing import Type
from vpy.lib.transformers.method_selection import SelectMethodsTransformer

from vpy.lib.utils import parse_class, remove_decorators
import vpy.lib.lookup as lookup
from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.lens import LensTransformer
from vpy.typechecker.checker import check_cls


def tr_class(mod, cls: Type, v: VersionId) -> ClassDef:
    cls_ast, g = parse_class(cls)
    tr_cls_ast = copy.deepcopy(cls_ast)
    status, err = check_cls(cls)
    if not status:
        raise Exception(err)
    bases = {}
    fields = {}
    lenses = {}
    for k in g.nodes:
        base = lookup.base(g, cls_ast, k.name)
        if base is not None:
            bases[k.name], fields[k.name] = base
    for k in g.nodes:
        for t in g.nodes:
            if k != t:
                #TODO: base version or not?
                if bases[k.name] not in lenses:
                    lenses[bases[k.name]] = {}
                if (lens := lookup.lens_lookup(
                    g, k.name, t.name, tr_cls_ast)):
                    lenses[bases[k.name]][bases[t.name]] = lens
    tr_cls_ast = SelectMethodsTransformer(g=g, v=v).visit(tr_cls_ast)
    tr_cls_ast = LensTransformer(g=g,
                                 cls_ast=tr_cls_ast,
                                 bases=bases,
                                 fields=fields,
                                 get_lenses=lenses,
                                 target=v).visit(tr_cls_ast)
    tr_cls_ast.name += '_' + v
    if tr_cls_ast.body == []:
        tr_cls_ast.body.append(ast.Pass())
    return remove_decorators(tr_cls_ast)
