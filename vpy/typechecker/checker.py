from ast import Attribute, Call, ClassDef, fix_missing_locations, walk
from types import ModuleType

from networkx import find_cycle
from networkx.exception import NetworkXNoCycle
from vpy.lib.lib_types import Environment, Graph
from vpy.lib.lookup import _method_lookup
from vpy.lib.utils import (
    annotation_from_type_value,
    fields_in_function,
    get_at,
    get_module_environment,
    graph,
    parse_module,
    typeof_node,
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
    status = True
    err = []
    for node in mod_ast.body:
        if isinstance(node, ClassDef):
            cls_status, cls_err = check_cls(module, node, mod_env)
            if not cls_status:
                status = False
                err += cls_err
    return (status, err)


def check_cls(
    module: ModuleType, cls_ast: ClassDef, env: Environment
) -> tuple[bool, list[str]]:
    g = graph(cls_ast)
    for check in [
        check_version_graph,
        check_methods,
        check_missing_field_lenses,
        check_method_lenses,
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
                        f"Conflict in method {m[0].name} of class {cls_ast.name}:"
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
            for w in lenses.get(v.name, {}).values()
            for l in w.values()
            if l.node is not None
        }
        for m in methods.union(lenses_methods):
            if isinstance(m, tuple):
                assert False
            mver = get_at(m)
            if mver != v.name and mver not in env.bases[cls_ast.name][v.name]:
                for field in env.fields[cls_ast.name][mver]:
                    if (
                        field.name not in lenses[mver]
                        or v.name not in lenses[mver][field.name]
                    ):
                        return (
                            False,
                            [
                                f"No path between versions {mver} and {v.name} for field {field.name}"
                            ],
                        )
    return (True, [])


def check_method_lenses(g: Graph, cls_ast: ClassDef, env: Environment):
    lenses = env.method_lenses[cls_ast.name]
    for v, v_lenses in lenses.items():
        for method, m_lenses in v_lenses.items():
            for t, lens in m_lenses.items():
                lens_node = lens.node
                if lens_node is None:
                    continue
                m_v = _method_lookup(
                    Graph(graph={v: g.find_version(v)}),
                    cls_ast,
                    method,
                    v,
                )
                m_t = _method_lookup(
                    Graph(graph={t: g.find_version(t)}),
                    cls_ast,
                    method,
                    t,
                )
                if m_v is not None and m_t is not None:
                    lens_node.args.args[0].arg == "self"
                    lens_node.args.args[1].arg == "f"
                    lens_sig = env.visitor.visit(lens_node).signature
                    m_v_sig = env.visitor.visit(m_v).signature
                    if (
                        list(lens_sig.parameters.items())[2:]
                        != list(m_v_sig.parameters.items())[1:]
                    ):
                        return (
                            False,
                            [
                                f"""Wrong signature in lens of method {method} from version {v} to {t}. The signature must match that of {method} in version {v}:
def {lens_node.name}(self, f: Callable, {','.join(p.name for p in list(m_v_sig.parameters.values())[1:])}) -> {str(m_v_sig.return_value)}"""
                            ],
                        )
                    if lens_sig.return_value != m_v_sig.return_value:
                        return (
                            False,
                            [
                                f"""Wrong signature in lens of method {method} from version {v} to {t}. The signature must match that of {method} in version {v}:
def {lens_node.name}(self, f: Callable, {','.join(p.name for p in list(m_v_sig.parameters.values())[1:])}) -> {str(m_v_sig.return_value)}"""
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
        for m in methods:

            mdef = _method_lookup(
                Graph(graph={v.name: v}),
                cls_ast,
                m.name,
                v.name,
            )
            if mdef is not None and get_at(m) != get_at(mdef):
                # TODO: Pyanalyze does not store the (inferred) return type of functions in the AST node.
                # For now, let's make return annotation mandatory (pyanalyze can type check the body to match the annotation).
                if mdef.returns is None:
                    return (
                        False,
                        [
                            f"""Missing return type annotation for method {mdef.name} in version {get_at(mdef)}"""
                        ],
                    )
                if m.returns is None:
                    return (
                        False,
                        [
                            f"""Missing return type annotation for method {m.name} in version {get_at(m)}"""
                        ],
                    )
                m_sig = env.visitor.visit(m).signature
                mdef_sig = env.visitor.visit(mdef).signature
                if (
                    lenses.find_lens(v_from=v.name, v_to=get_at(m), field_name=m.name)
                    is None
                ):
                    # TODO: Naive approach to compare signatures (they must be the same).
                    # Refine with subtypes, optional arguments, etc.
                    if (
                        (len(m_sig.parameters) != len(mdef_sig.parameters))
                        or (m_sig != mdef_sig)
                        or (m_sig.return_value != mdef_sig.return_value)
                    ):
                        return (
                            False,
                            [
                                f"""Missing method lens between versions {v.name} and {get_at(m)} for method {m.name}"""
                            ],
                        )
            # elif get_at(m) != v.name:
            #     for node in walk(m):
            #         if isinstance(node, Call) and isinstance(node.func, Attribute):
            #             obj_type = annotation_from_type_value(
            #                 typeof_node(node.func.value)
            #             )
            #             if obj_type == cls_ast.name:
            #                 callee_t = [
            #                     m
            #                     for m in env.methods[cls_ast.name][get_at(m)]
            #                     if m.name == node.func.attr
            #                 ][0]
            #                 callee_t_sig = env.visitor.visit(callee_t).signature
            #                 m_sig = env.visitor.visit(m).signature
            #                 if (
            #                     lenses.find_lens(
            #                         v_from=get_at(m),
            #                         v_to=get_at(callee_t),
            #                         field_name=callee_t.name,
            #                     )
            #                     is None
            #                 ):
            #                     if get_at(m) != get_at(callee_t) and (
            #                         (
            #                             len(m_sig.parameters)
            #                             != len(callee_t_sig.parameters)
            #                         )
            #                         or (m_sig != callee_t_sig)
            #                         or (m_sig.return_value != mdef_sig.return_value)
            #                     ):
            #                         return (
            #                             False,
            #                             [
            #                                 f"""Missing method lens between versions {get_at(m)} and {get_at(callee_t)} for method {callee_t.name}"""
            #                             ],
            #                         )
    return (True, [])
