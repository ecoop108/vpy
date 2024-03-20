import ast
from ast import ClassDef, FunctionDef, NodeVisitor
from vpy.lib.lib_types import Field, Graph, Lenses, VersionId, VersionedMethod
from vpy.lib.utils import (
    fields_in_function,
    get_decorators,
    is_lens,
    get_at,
)
from vpy.lib.visitors.fields import ClassFieldCollector


def base_versions(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[VersionId]:
    fields_v = fields_at(g=g, cls_ast=cls_ast, v=v)
    if len(fields_v) > 0:
        return {v}
    else:
        base_p: set[VersionId] = set()
        for p in g.parents(v):
            back = base_versions(g, cls_ast, p)
            base_p = base_p.union(back)
        return base_p


def field_lenses_lookup(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses = Lenses()
    for k in g.all():
        for t in g.all():
            if k != t:
                lens = __field_lens_lookup(g, k.name, t.name, cls_ast)
                if len(lens) == 0 and k.name not in lenses.data:
                    lenses.data[k.name] = {}
                else:
                    for field, lens_node in lens.items():
                        lenses.add_lens(
                            v_from=k.name,
                            field_name=field.name,
                            v_to=t.name,
                            lens_node=lens_node,
                        )
    return lenses


def method_lenses_lookup(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses = Lenses()
    for k in g.all():
        for t in g.all():
            if k != t:
                if lens := __method_lens_lookup(g, k.name, t.name, cls_ast):
                    for method, lens_node in lens.items():
                        lenses.add_lens(
                            v_from=k.name,
                            field_name=method,
                            v_to=t.name,
                            lens_node=lens_node,
                        )
    return lenses


def fields_lookup(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[Field]:
    """
    Returns the set of fields defined for version v.
    These may be explictly defined at v or inherited from some other related version(s).
    """

    base_v = base_versions(g, cls_ast, v)
    base_fields: set[Field] = set()
    if base_v == {v}:
        return fields_at(g, cls_ast, v)
    else:
        for w in base_v:
            base_fields = base_fields.union(fields_lookup(g, cls_ast, w))
        return base_fields


def methods_lookup(
    g: Graph, cls_ast: ClassDef, v: VersionId
) -> set[VersionedMethod | tuple[FunctionDef]]:
    """
    Returns the methods of a class available at version v. These may be
    explictly defined at v or inherited from some other related version(s).
    """

    class MethodCollector(NodeVisitor):
        def __init__(self):
            self.methods: set[VersionedMethod | tuple[FunctionDef]] = set()

        def visit_ClassDef(self, node: ClassDef):
            self.generic_visit(node)

        def visit_FunctionDef(self, node: FunctionDef):
            if not is_lens(node):
                mdef = _method_lookup(g, cls_ast, node.name, v)
                if mdef is not None:
                    self.methods.add(mdef)

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods


# Auxiliary methods


def __lenses_at(
    g: Graph, cls_ast: ClassDef, v: VersionId
) -> dict[str, dict[VersionId, FunctionDef]]:
    """
    Returns the lenses explicitly defined at version v.
    """
    lenses: dict[str, dict[VersionId, FunctionDef]] = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            decorators = get_decorators(method, "get")
            if len(decorators) > 0:
                decorator = decorators[0]
                at, target, field = [
                    a.value for a in decorator.args if isinstance(a, ast.Constant)
                ]
                if (
                    v == target
                    and g.find_version(v) is not None
                    and g.find_version(target) is not None
                ):
                    if field not in lenses:
                        lenses[field] = {}
                    lenses[field][at] = method
    return lenses


def __field_lens_path_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef, field: str
) -> list[FunctionDef] | None:
    """
    Returns a list of lenses to rewrite field from version v to version t
    """
    lenses = __lenses_at(g=g, cls_ast=cls_ast, v=v)
    if field not in lenses:
        bases_v = base_versions(g, cls_ast, v)
        if bases_v != {v}:
            result = []
            for w in bases_v:
                path = __field_lens_path_lookup(g, w, t, cls_ast, field)
                if path is not None:
                    result += path
            if result != []:
                return result
        return None
    if t in lenses[field]:
        return [lenses[field][t]]
    else:
        base_t = base_versions(g, cls_ast, t)
        for w, lens in lenses[field].items():
            if w in base_t:
                return __field_lens_path_lookup(g, v, w, cls_ast, field)
            result = [lens]
            fields_w = fields_lookup(g, cls_ast, w)
            references = fields_in_function(lens, fields_w)
            for ref in references:
                path = __field_lens_path_lookup(g.delete(v), w, t, cls_ast, ref.name)
                if path is None:
                    break
                result += path
            else:
                return result
        return None


def __method_lens_path_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef, method: str
) -> list[dict[str, FunctionDef]] | None:
    """
    Returns a list of lenses to rewrite method from version v to version t
    """
    lenses = __lenses_at(g=g, cls_ast=cls_ast, v=t)
    if method not in lenses:
        return None
    if v in lenses[method]:
        return [{method: lenses[method][v]}]
    else:
        for w, lens in lenses[method].items():
            result = [{method: lens}]
            methods_w = methods_at(g, cls_ast, w)
            for m in methods_w:
                path = __method_lens_path_lookup(g.delete(v), w, t, cls_ast, m.name)
                if path is None:
                    break
                result += path
            else:
                return result
        return None


def __field_lens_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef
) -> dict[Field, FunctionDef | None]:
    """
    Returns the field lenses from v to t.
    """
    fields_v = fields_lookup(g, cls_ast, v)
    result: dict[Field, FunctionDef | None] = {}
    bases_v = base_versions(g, cls_ast, v)
    bases_t = base_versions(g, cls_ast, t)
    for field in fields_v:
        if bases_v <= bases_t:
            result[field] = None
        else:
            path = __field_lens_path_lookup(g, v, t, cls_ast, field.name)
            if path is not None:
                lens = path[0]
                result[field] = lens
    return result


def __method_lens_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef
) -> dict[str, FunctionDef]:
    """
    Returns the method lenses from v to t.
    """
    methods_v = methods_at(g, cls_ast, v)
    result: dict[str, FunctionDef] = {}
    for method in methods_v:
        path = __method_lens_path_lookup(g, v, t, cls_ast, method.name)
        if path is not None:
            lens = path[0][method.name]
            result[method.name] = lens
    return result


def __replacement_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    """
    Search for a replacement implementation of method `m` for version `v`.
    """
    if m == "__init__":
        return None
    replacements = g.replacements(v)
    rm: set[FunctionDef] = set()
    for me in set(
        _method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements
    ):
        if me is not None:
            if not isinstance(me, VersionedMethod):
                rm.union(set(me))
            else:
                version_v = g.find_version(v)
                if version_v is not None:
                    if get_at(me.implementation) in [
                        r for r in version_v.replaces
                    ] and (lm := __local_method_lookup(cls_ast=cls_ast, m=m, v=v)):
                        return lm
                rm.add(me.implementation)
    if len(rm) == 0:
        return None
    if len(rm) == 1:
        mv = get_at(list(rm)[0])
        ge = g.delete(v)
        ge = g.delete(mv)
        me = _method_lookup(ge, cls_ast, m, v)
        if me is not None and not isinstance(me, VersionedMethod):
            return me

    return tuple(rm)


def __local_method_lookup(
    cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    """
    Search for a local implementation of method `m` for version `v`.
    """
    methods = tuple(
        set(
            m
            for m in cls_ast.body
            if isinstance(m, ast.FunctionDef) and not is_lens(m) and get_at(m) == v
        )
    )
    lm = tuple(
        set(me for me in [me for me in methods if me.name == m] if me is not None)
    )
    # if len(lm) == 0 and m in dir(object):
    #     return tuple()
    return lm if len(lm) > 0 else None


def __inherited_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    """
    Search for an inherited implementation of method `m` for version `v`.
    """
    graph = g.delete(v)
    um: set[FunctionDef] = set()
    for me in [_method_lookup(graph, cls_ast, m, r) for r in g.parents(v)]:
        if me is not None:
            if not isinstance(me, VersionedMethod):
                um.union(set(me))
            else:
                um.add(me.implementation)
    return tuple(um) if len(um) > 0 else None


def _method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> VersionedMethod | tuple[FunctionDef, ...] | None:
    if g.find_version(v) is None:
        return None
    interface = implementation = None
    rm = __replacement_method_lookup(g, cls_ast, m, v)
    if rm is not None:
        if len(rm) == 1:
            implementation = interface = rm[0]
        else:
            return rm

    lm = __local_method_lookup(cls_ast, m, v)
    if lm is not None:
        if len(lm) == 1:
            interface = lm[0]
            if implementation is None:
                implementation = lm[0]
        else:
            return lm

    um = __inherited_method_lookup(g, cls_ast, m, v)
    if um is not None:
        if len(um) == 1:
            if interface is None:
                interface = um[0]
            if implementation is None:
                implementation = um[0]
        else:
            return um
    if interface is not None and implementation is not None:
        return VersionedMethod(interface=interface, implementation=implementation)
    return None


def methods_at(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[FunctionDef]:
    """
    Returns the methods of a class explicitly defined at version v.
    """

    class MethodCollector(NodeVisitor):
        def __init__(self):
            self.methods = set()

        def visit_ClassDef(self, node: ClassDef):
            self.generic_visit(node)

        def visit_FunctionDef(self, node: FunctionDef):
            if not is_lens(node) and get_at(node) == v:
                self.methods.add(node)

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods


def fields_at(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[Field]:
    """
    Returns the set of fields explicitly defined at version v.
    """
    methods = methods_at(g, cls_ast, v)
    visitor = ClassFieldCollector(cls_ast, [m.name for m in methods], v)
    for m in methods:
        visitor.visit(m)
    parent_fields = {f for p in g.parents(v) for f in fields_at(g, cls_ast, p)}
    return {
        f
        for f in visitor.fields
        if all(
            f.name != pf.name or f.type.simplify() != pf.type.simplify()
            for pf in parent_fields
        )
    }
