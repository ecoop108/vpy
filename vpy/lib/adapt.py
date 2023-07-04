import ast
from ast import ClassDef
from collections import defaultdict
import copy
from vpy.lib.transformers.method_selection import SelectMethodsTransformer

from vpy.lib.utils import graph, remove_decorators
from vpy.lib import lookup
from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.lens import MethodRewriteTransformer
from vpy.typechecker.checker import check_cls


def tr_class(mod, cls_ast: ClassDef, v: VersionId) -> ClassDef:
    g = graph(cls_ast)
    status, err = check_cls(mod, cls_ast)
    if not status:
        raise Exception(err)
    fields = {}
    lenses = lookup.cls_lenses(g, cls_ast)
    for k in g.all():
        fields[k.name] = lookup.base(g, cls_ast, k.name)[1]
        for t in g.all():
            if k != t:
                if k.name not in lenses:
                    lenses[k.name] = defaultdict(dict)
                if (lens := lookup.lens_lookup(
                    g, k.name, t.name, cls_ast)):
                    for field, lens_node in lens.items():
                        lenses[k.name][field][t.name] = lens_node
    cls_ast = SelectMethodsTransformer(g=g, v=v).visit(cls_ast)
    cls_ast = MethodRewriteTransformer(g=g,
                                 cls_ast=cls_ast,
                                 fields=fields,
                                 get_lenses=lenses,
                                 target=v).visit(cls_ast)
    cls_ast.name += '_' + v
    if cls_ast.body == []:
        cls_ast.body.append(ast.Pass())
    return remove_decorators(cls_ast)
