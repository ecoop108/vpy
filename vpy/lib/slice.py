import ast
from collections import defaultdict
from types import ModuleType
from typing import Type

from vpy.lib import lookup

from vpy.lib.lib_types import Environment, VersionId
from vpy.lib.transformers.cls import ClassTransformer
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer
from vpy.lib.transformers.module import ModuleTransformer
from vpy.lib.utils import parse_class, parse_module
from vpy.typechecker.checker import check_cls


def rw_module(module: ModuleType, v: VersionId):  # -> ModuleType
    mod_ast = ModuleTransformer(v).visit(parse_module(module))
    return [ast.unparse(ast.fix_missing_locations(mod_ast))]


def eval_slice(module: ModuleType, cls: Type, v: VersionId) -> Type:
    cls_ast, g = parse_class(module, cls)
    status, err = check_cls(module, cls_ast)
    if not status:
        raise Exception(err)
    lenses = lookup.cls_lenses(g, cls_ast)
    fields = {}
    for k in g.all():
        if cls_ast.name not in fields:
            fields[cls_ast.name] = {}
        fields[cls_ast.name][k.name] = lookup.fields_lookup(g, cls_ast, k.name)
        for t in g.all():
            if k != t:
                if k.name not in lenses:
                    lenses[k.name] = defaultdict(dict)
                if lens := lookup.lens_lookup(g, k.name, t.name, cls_ast):
                    for field, lens_node in lens.items():
                        lenses[k.name][field][t.name] = lens_node
    env = Environment(fields=fields, get_lenses=lenses, put_lenses=[])
    sl = ClassTransformer(v=v, env=env).visit(cls_ast)
    s = ast.unparse(ast.fix_missing_locations(sl))
    out = [type]
    exec(s + f"\nout[0]={cls.__name__}_{v}")
    return out[0]
