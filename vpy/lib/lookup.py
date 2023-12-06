from _ast import FunctionDef
import ast
from ast import ClassDef, FunctionDef, NodeVisitor
from vpy.lib.lib_types import Field, Field, Graph, Lenses, VersionId
from vpy.lib.utils import (
    ClassFieldCollector,
    fields_in_function,
    get_decorator,
    is_lens,
    get_at,
)


def base(g: Graph, cls_ast: ClassDef, v: VersionId) -> VersionId | None:
    fields_v = fields_at(g=g, cls_ast=cls_ast, v=v)
    if len(fields_v) > 0:
        return v
    else:
        base_p = None
        for p in g.parents(v):
            back = base(g, cls_ast, p)
            if base_p:
                if back != base_p:
                    return None
            else:
                base_p = back
        return base_p


def cls_field_lenses(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses = Lenses()
    for k in g.all():
        for t in g.all():
            if k != t:
                if lens := __lens_lookup(g, k.name, t.name, cls_ast):
                    for field, lens_node in lens.items():
                        lenses.put(
                            v_from=k.name,
                            field_name=field.name,
                            v_to=t.name,
                            lens_node=lens_node,
                        )
    return lenses


def cls_method_lenses(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses = Lenses()
    for k in g.all():
        for t in g.all():
            if k != t:
                if lens := __method_lens_lookup(g, k.name, t.name, cls_ast):
                    for method, lens_node in lens.items():
                        lenses.put(
                            v_from=k.name,
                            field_name=method,
                            v_to=t.name,
                            lens_node=lens_node,
                        )
    return lenses


def __lenses_to(
    g: Graph, cls_ast: ClassDef, v: VersionId
) -> dict[str, dict[VersionId, FunctionDef]]:
    """
    Returns the lenses explicitly defined at version v.
    """
    lenses = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            decorator = get_decorator(method, "get")
            if decorator:
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


# TODO: Add identity lens here
def field_lens_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef, field: str
) -> list[dict[str, FunctionDef]] | None:
    """
    Returns a list of lenses to rewrite field from version v to version t
    """
    lenses = __lenses_to(g=g, cls_ast=cls_ast, v=v)
    if field not in lenses:
        return None
    if t in lenses[field]:
        return [{field: lenses[field][t]}]
    else:
        for w, lens in lenses[field].items():
            result = [{field: lens}]
            fields_w = fields_lookup(g, cls_ast, w)
            references = fields_in_function(lens, fields_w)
            for ref in references:
                path = field_lens_lookup(g.delete(v), w, t, cls_ast, ref.name)
                if path is None:
                    break
                result += path
            else:
                return result
        return None


def method_lens_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef, method: str
) -> list[dict[str, FunctionDef]] | None:
    """
    Returns a list of lenses to rewrite method from version v to version t
    """
    lenses = __lenses_to(g=g, cls_ast=cls_ast, v=t)
    if method not in lenses:
        return None
    if v in lenses[method]:
        return [{method: lenses[method][v]}]
    else:
        for w, lens in lenses[method].items():
            result = [{method: lens}]
            methods_w = methods_at(g, cls_ast, w)
            for m in methods_w:
                path = method_lens_lookup(g.delete(v), w, t, cls_ast, m.name)
                if path is None:
                    break
                result += path
            else:
                return result
        return None


def __lens_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef
) -> dict[Field, FunctionDef | None]:
    """
    Returns the lenses from v to t.
    """ 
    fields_v = fields_lookup(g, cls_ast, v)
    result: dict[Field, FunctionDef | None] = {}
    for field in fields_v:
        if base(g, cls_ast, t) == v:
           result[field] = None
        else:
            path = field_lens_lookup(g, v, t, cls_ast, field.name)
            if path is not None:
                lens = path[0][field.name]
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
        path = method_lens_lookup(g, v, t, cls_ast, method.name)
        if path is not None:
            lens = path[0][method.name]
            result[method.name] = lens
    return result


def __replacement_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    if m == "__init__":
        return None
    replacements = g.replacements(v)
    rm = set()
    for me in [_method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements]:
        if me is not None:
            if isinstance(me, tuple):
                rm.union(set(me))
            else:
                if get_at(me) in [r for r in g.find_version(v).replaces] and (
                    lm := __local_method_lookup(cls_ast=cls_ast, m=m, v=v)
                ):
                    return lm
                rm.add(me)
    return tuple(rm) if len(rm) > 0 else None


def __local_method_lookup(
    cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    # inherited_methods = [m for m in cls_ast.bases]

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
    if len(lm) == 0 and m in dir(object):
        return tuple()
    return lm if len(lm) > 0 else None


def __inherited_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> tuple[FunctionDef, ...] | None:
    graph = g.delete(v)
    um = set()
    for me in [_method_lookup(graph, cls_ast, m, r) for r in g.parents(v)]:
        if me is not None:
            if isinstance(me, tuple):
                um.union(set(me))
            else:
                um.add(me)
    return tuple(um) if len(um) > 0 else None


def _method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> FunctionDef | tuple[FunctionDef, ...] | None:
    if g.find_version(v) is None:
        return None
    rm = __replacement_method_lookup(g, cls_ast, m, v)
    if rm is not None:
        if len(rm) == 1:
            return rm[0]
        return rm

    lm = __local_method_lookup(cls_ast, m, v)
    if lm is not None:
        if len(lm) == 1:
            return lm[0]
        return lm

    um = __inherited_method_lookup(g, cls_ast, m, v)
    if um is not None:
        if len(um) == 1:
            return um[0]
        return um
    return None


def fields_lookup(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[Field]:
    """
    Returns the set of fields defined for version v.
    These may be explictly defined at v or inherited from some other related version(s).
    """

    if (base_v := base(g, cls_ast, v)) is not None:
        return fields_at(g, cls_ast, base_v)
    inherited = set()
    for p in g.parents(v):
        fields = fields_lookup(g.delete(v), cls_ast, p)
        for field in fields:
            inherited.add(field)
    return inherited


def methods_lookup(
    g: Graph, cls_ast: ClassDef, v: VersionId
) -> set[FunctionDef | tuple[FunctionDef]]:
    """
    Returns the methods of a class available at version v.
    """

    class MethodCollector(NodeVisitor):
        def __init__(self):
            self.methods = set()

        def visit_ClassDef(self, node: ClassDef):
            self.generic_visit(node)

        def visit_FunctionDef(self, node: FunctionDef):
            if not is_lens(node):
                mdef = _method_lookup(g, cls_ast, node.name, v)
                if mdef is not None:
                    if isinstance(mdef, tuple):
                        if get_at(node) in [get_at(m) for m in mdef]:
                            self.methods.add(mdef)
                    else:
                        if get_at(node) == get_at(mdef):
                            self.methods.add(mdef)

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods


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
            f.name != pf.name or not f.type.simplify() == pf.type.simplify()
            for pf in parent_fields
        )
    }
