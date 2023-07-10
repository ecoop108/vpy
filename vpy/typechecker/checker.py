from ast import ClassDef
from types import ModuleType

from networkx import find_cycle
from networkx.exception import NetworkXNoCycle
from vpy.lib.lib_types import Graph
from vpy.lib.lookup import fields_lookup, field_lens_lookup, lens_lookup, method_lookup, methods_at
from vpy.lib.utils import FieldReferenceCollector, get_at, get_self_obj, graph, parse_module

def check_module(module: ModuleType):
    mod_ast = parse_module(module)
    for node in mod_ast.body:
        if isinstance(node, ClassDef):
            return check_cls(module, node)
    # return check_cls(module)


def check_cls(module: ModuleType, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    g = graph(cls_ast)
    # cls_ast, g = parse_class(module, cls)
    for check in [check_version_graph, check_methds, check_missing_lenses]:
        status, err = check(g, cls_ast)
        if not status:
            return (False, err)
    return (True, [])


def check_version_graph(g: Graph, cls_ast: ClassDef):
    try:
        find_cycle(g)
        return (False, ['Invalid version graph.'])
    except NetworkXNoCycle:
        return (True, [])


def check_methds(g: Graph, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    for v in g.all():
        for m in methods_at(g, cls_ast, v.name):
            for w in g.children(v.name):
                if method_lookup(g, cls_ast, m.name, w.name) is None:
                    return (False, [f'Conflict  {v, w}: {m.name} '])
    return (True, [])


def check_missing_lenses(g: Graph,
                         cls_ast: ClassDef) -> tuple[bool, list[str]]:
    # lenses = cls_lenses(g, cls_ast)
    for v in g.all():
        for m in methods_at(g, cls_ast, v.name):
            mver = get_at(m)
            if mver != v.name:
                _, fields_m = fields_lookup(g, cls_ast, mver)
                visitor = FieldReferenceCollector(get_self_obj(m), fields_m)
                visitor.visit(m)
                path = lens_lookup(g, mver, v.name, cls_ast)
                for ref in visitor.references:
                    path = field_lens_lookup(g, mver, v.name, cls_ast, ref)
                    if path is None:
                        return (False, [
                            f'No path between versions {mver} and {v.name} for field {ref} in method {m.name}'
                        ])
    return (True, [])
