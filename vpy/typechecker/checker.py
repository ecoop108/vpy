from ast import ClassDef, fix_missing_locations
from types import ModuleType

from networkx import find_cycle
from networkx.exception import NetworkXNoCycle
from vpy.lib import lookup
from vpy.lib.lib_types import Graph
from vpy.lib.lookup import (
    base,
    cls_field_lenses,
    fields_at,
    fields_lookup,
    field_lens_lookup,
    methods_lookup,
)
from vpy.lib.utils import (
    create_identity_lens,
    create_init,
    fields_in_function,
    get_at,
    graph,
    parse_module,
)


# class ErrorCode(enum.Enum):
#     found_assert = 1
#     found_import = 2


# class BadStatementFinder(node_visitor.BaseNodeVisitor):
#     error_code_enum = ErrorCode

#     def visit_ClassDef(self, node: ClassDef) -> Any:
#         g = graph(node)
#         self.g = g
#         self.cls_ast = node
#         self.generic_visit(node)

#     def visit_FunctionDef(self, node: FunctionDef) -> Any:
#         for v in self.g.all():
#             for m in methods_lookup(g, cls_ast, v.name):
#                 for w in g.children(v.name):
#                     if m.name not in [
#                         m.name for m in methods_lookup(g, cls_ast, w.name)
#                     ]:
#                         return (False, [f"Conflict  {v, w}: {m.name} "])
#         return (True, [])

#         return super().visit_FunctionDef(node)

#     def visit_Import(self, node):
#         self.show_error(node, error_code=ErrorCode.found_import)


def check_module(module: ModuleType) -> tuple[bool, list[str]]:
    mod_ast = parse_module(module)
    for node in mod_ast.body:
        if isinstance(node, ClassDef):
            return check_cls(module, node)
    return (True, [])
    # return check_cls(module)


def check_cls(module: ModuleType, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    g = graph(cls_ast)
    # cls_ast, g = parse_class(module, cls)
    for v in g.all():
        if base(g, cls_ast, v.name) is None:
            cls_ast.body.append(create_init(g=g, cls_ast=cls_ast, v=v.name))
            for w in g.parents(v.name):
                for field in lookup.fields_lookup(g, cls_ast, w):
                    cls_ast.body.append(
                        create_identity_lens(g, cls_ast, v.name, w, field)
                    )
                    cls_ast.body.append(
                        create_identity_lens(g, cls_ast, w, v.name, field)
                    )
    cls_ast = fix_missing_locations(cls_ast)
    for check in [
        check_version_graph,
        check_state,
        check_methods,
        check_missing_lenses,
    ]:
        status, err = check(g, cls_ast)
        if not status:
            return (False, err)
    return (True, [])


def check_version_graph(g: Graph, cls_ast: ClassDef):
    try:
        find_cycle(g)
        return (False, ["Invalid version graph."])
    except NetworkXNoCycle:
        return (True, [])


def check_state(g: Graph, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    # for v in g.all():
    #     if base(g, cls_ast, v.name) is None:
    #         return (
    #             False,
    #             [
    #                 f"State conflict in version {v.name}: merge state of {g.parents(v.name)}"
    #             ],
    #         )
    return (True, [])


def check_methods(g: Graph, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    for v in g.all():
        for m in methods_lookup(g, cls_ast, v.name):
            if isinstance(m, tuple):
                return (
                    False,
                    [
                        f"Conflict {m[0].name}: {v, [get_at(n) for n in m if get_at(n) != v]}"
                    ],
                )
    return (True, [])


def check_missing_lenses(g: Graph, cls_ast: ClassDef) -> tuple[bool, list[str]]:
    # cls_ast = copy.deepcopy(cls_ast)
    lenses = cls_field_lenses(g, cls_ast)
    for v in g.all():
        methods = methods_lookup(g, cls_ast, v.name)
        lenses_methods = []  # l for w in lenses[v.name].values() for l in w.values()]
        for m in methods.union(set(lenses_methods)):
            if isinstance(m, tuple):
                assert False
            mver = get_at(m)
            fields_v = fields_at(g=g, cls_ast=cls_ast, v=v.name)
            if mver != v.name and len(fields_v) > 0:
                fields_m = fields_lookup(g, cls_ast, mver)
                references = fields_in_function(node=m, fields=fields_m)
                for ref in references:
                    path = field_lens_lookup(g, mver, v.name, cls_ast, ref.name)
                    if path is None:
                        return (
                            False,
                            [
                                f"No path between versions {mver} and {v.name} for field {ref.name} in method {m.name}"
                            ],
                        )
    return (True, [])
