import ast
from collections import defaultdict
from types import ModuleType
from typing import Type

from vpy.lib import lookup

from vpy.lib.lib_types import Environment, VersionId
from vpy.lib.transformers.cls import ClassTransformer
from vpy.lib.utils import parse_class
from vpy.typechecker.checker import check_cls


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    #TODO: Fix this
    cls_ast, g = parse_class(module, cls)
    status, err = check_cls(module, cls_ast)
    if not status:
        raise Exception(err)
    lenses = lookup.field_lenses_lookup(g, cls_ast)
    fields = {}
    bases = {}
    for k in g.all():
        if cls_ast.name not in fields:
            fields[cls_ast.name] = {}
        fields[cls_ast.name][k.name] = lookup.fields_lookup(g, cls_ast, k.name)
        bases[k.name] = lookup.base(g, cls_ast, k.name)
        for t in g.all():
            if k != t:
                if k.name not in lenses:
                    lenses[k.name] = defaultdict(dict)
                if lens := lookup.__lens_lookup(g, k.name, t.name, cls_ast):
                    for field, lens_node in lens.items():
                        lenses[k.name][field.name][t.name] = lens_node
    env = Environment(fields=fields, get_lenses=lenses, put_lenses=[], bases=bases)
    sl = ClassTransformer(v=v, env=env).visit(cls_ast)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [type]
    exec(s + f"\nout[0]={cls.__name__}_{v}")
    return out[0]
