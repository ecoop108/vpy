from ast import ClassDef, fix_missing_locations
from types import ModuleType

from networkx import find_cycle
from networkx.exception import NetworkXNoCycle
from vpy.lib.lib_types import Environment, Graph
from vpy.lib.lookup import _method_lookup
from vpy.lib.utils import (
    fields_in_function,
    get_at,
    get_module_environment,
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
    mod_ast, visitor = parse_module(module)
    mod_env = get_module_environment(mod_ast)
    mod_env.visitor = visitor
    for node in mod_ast.body:
        if isinstance(node, ClassDef):
            return check_cls(module, node, mod_env)
    return (True, [])
    # return check_cls(module)


def check_cls(
    module: ModuleType, cls_ast: ClassDef, env: Environment
) -> tuple[bool, list[str]]:
    g = graph(cls_ast)
    for check in [
        check_version_graph,
        check_methods,
        check_missing_field_lenses,
        check_missing_method_lenses,
    ]:
        status, err = check(g, cls_ast, env)
        if not status:
            return (False, err)
    return (True, [])


def check_version_graph(g: Graph, cls_ast: ClassDef, env: Environment):
    try:
        find_cycle(g)
        return (False, ["Invalid version graph."])
    except NetworkXNoCycle:
        return (True, [])


def check_methods(
    g: Graph, cls_ast: ClassDef, env: Environment
) -> tuple[bool, list[str]]:
    for v in g.all():
        for m in env.methods[cls_ast.name][v.name]:
            if isinstance(m, tuple):
                return (
                    False,
                    [
                        f"Conflict {m[0].name}:"
                        f" {v, [get_at(n) for n in m if get_at(n) != v]}"
                    ],
                )
    return (True, [])


def check_missing_field_lenses(
    g: Graph, cls_ast: ClassDef, env: Environment
) -> tuple[bool, list[str]]:
    lenses = env.get_lenses[cls_ast.name]
    for v in g.all():
        methods = env.methods[cls_ast.name][v.name]
        lenses_methods = {
            l.node
            for w in lenses[v.name].values()
            for l in w.values()
            if l.node is not None
        }
        for m in methods.union(lenses_methods):
            if isinstance(m, tuple):
                assert False
            mver = get_at(m)
            if mver != v.name and mver not in env.bases[cls_ast.name][v.name]:
                references = fields_in_function(
                    node=m, fields=env.fields[cls_ast.name][mver]
                )
                for ref in references:
                    if (
                        ref.name not in lenses[mver]
                        or v.name not in lenses[mver][ref.name]
                    ):
                        return (
                            False,
                            [
                                f"No path between versions {mver} and {v.name} for"
                                f" field {ref.name} in method {m.name}"
                            ],
                        )
    return (True, [])


# TODO: Check missing method lenses. If type is different? If signature is different?
def check_missing_method_lenses(
    g: Graph, cls_ast: ClassDef, env: Environment
) -> tuple[bool, list[str]]:
    lenses = env.method_lenses[cls_ast.name]
    for v in g.all():
        methods = env.methods[cls_ast.name][v.name]
        #     lenses_methods = {
        #         l.node
        #         for w in lenses[v.name].values()
        #         for l in w.values()
        #         if l.node is not None
        #     }
        #     # l for w in lenses[v.name].values() for l in w.values()]
        for m in methods:
            mdef = _method_lookup(
                Graph(graph={v.name: v}),
                cls_ast,
                m.name,
                v.name,
            )
            if (
                mdef is not None
                and get_at(m) != get_at(mdef)
                and env.visitor.get_local_return_value(
                    env.visitor.signature_from_value(m.inferred_value)
                )
                != env.visitor.get_local_return_value(
                    env.visitor.signature_from_value(mdef.inferred_value)
                )
            ):  # and method signatures are different (subtypes?) :
                if (
                    lenses.find_lens(v_from=v.name, v_to=get_at(m), field_name=m.name)
                    is None
                ):
                    return (
                        False,
                        [
                            f"""Missing method lens between versions {v.name} and {get_at(m)} for method {m.name}"""
                        ],
                    )
    return (True, [])
