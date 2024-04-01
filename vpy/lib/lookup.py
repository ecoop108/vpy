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
from vpy.lib.visitors.methods import MethodCollector


class MethodConflictException(Exception):
    def __init__(self, definitions, *, message=""):
        self.definitions: set[FunctionDef] = definitions
        super().__init__(message)


def base_versions(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[VersionId]:
    fields_v = fields_at(g=g, cls_ast=cls_ast, v=v)
    if len(fields_v) > 0:
        return {v}
    else:
        base_p: set[VersionId] = set()
        for p in g.parents(v):
            back = base_versions(g, cls_ast, p.name)
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
                            v_from=t.name,
                            v_to=k.name,
                            attr=field.name,
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
                            attr=method,
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


def methods_lookup(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[VersionedMethod]:
    """
    Returns the methods of a class available at version v. These may be
    explictly defined at v or inherited from some other related version(s).
    """

    class MethodCollector(NodeVisitor):
        def __init__(self):
            self.methods: set[VersionedMethod] = set()

        def visit_ClassDef(self, node: ClassDef):
            self.generic_visit(node)

        def visit_FunctionDef(self, node: FunctionDef):
            if not is_lens(node):
                try:
                    mdef = _method_lookup(g, cls_ast, node.name, v)
                    if mdef is not None:
                        self.methods.add(mdef)
                except MethodConflictException:
                    return

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods


# Auxiliary methods


# TODO: Refactor this, v should be first arg to decorator (at)
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


def __lenses_at_m(
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
                if v == at:
                    if field not in lenses:
                        lenses[field] = {}
                    lenses[field][target] = method
    return lenses


def __field_lens_path_lookup(
    g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef, field: str
) -> list[FunctionDef] | None:
    """
    Returns a list of lenses to rewrite field from version v to version t
    """
    # TODO: Fix this after refactoring __lenses_at
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
    # TODO: Do we need the method name in the result?
    """
    Returns a list of lenses to rewrite method from version v to version t.
    """
    lenses = __lenses_at_m(g=g, cls_ast=cls_ast, v=v)
    if method not in lenses:
        return None
    if t in lenses[method]:
        return [{method: lenses[method][t]}]
    else:
        for w, lens in lenses[method].items():
            result = [{method: lens}]
            methods_w = methods_at(cls_ast, w)
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
        if bases_v <= bases_t or field in fields_lookup(g, cls_ast, t):
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
    methods_v = methods_at(cls_ast, v)
    result: dict[str, FunctionDef] = {}
    for method in methods_v:
        path = __method_lens_path_lookup(g, v, t, cls_ast, method.name)
        if path is not None:
            lens = path[0][method.name]
            result[method.name] = lens
    return result


def __replacement_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> FunctionDef | None:
    """
    Search for a replacement implementation of method `m` for version `v`.
    """
    if m == "__init__":
        return None
    rm: set[FunctionDef] = set()
    gr = g.delete(v)
    for r in g.replacements(v):
        try:
            me = _method_lookup(g, cls_ast, m, r.name)
            if me is not None:
                #     version_v = g.find_version(v)
                #     if version_v is not None:
                #         try:
                #             if get_at(me.implementation) in [
                #                 r for r in version_v.replaces
                #             ] and (lm := __local_method_lookup(cls_ast=cls_ast, m=m, v=v)):
                #                 return lm
                #         except MethodConflictException:
                #             continue
                rm.add(me.implementation)
        except MethodConflictException as e:
            rm = rm.union(e.definitions)
    if len(rm) == 0:
        return None
    if len(rm) == 1:
        mv = get_at(list(rm)[0])
        ge = g.delete(v).delete(mv)
        try:
            me = _method_lookup(ge, cls_ast, m, v)
            return rm.pop()
        except MethodConflictException as e:
            raise e

    raise MethodConflictException(definitions=rm)


def __local_method_lookup(
    cls_ast: ClassDef, m: str, v: VersionId
) -> FunctionDef | None:
    """
    Search for a local implementation of method `m` for version `v`.
    """
    methods = methods_at(cls_ast, v)
    lm = list(me for me in methods if me.name == m)
    if len(lm) == 0:
        return None
    if len(lm) == 1:
        return lm[0]
    raise MethodConflictException(definitions=lm)


def __inherited_method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> FunctionDef | None:
    """
    Search for an inherited implementation of method `m` for version `v`.
    """
    graph = g.delete(v)
    um: set[FunctionDef] = set()
    for p in g.parents(v):
        try:
            me = _method_lookup(graph, cls_ast, m, p.name)
            if me is not None:
                um.add(me.implementation)
        except MethodConflictException as e:
            um = um.union(e.definitions)
    if len(um) == 0:
        return None
    if len(um) == 1:
        return um.pop()
    raise MethodConflictException(definitions=um)


def _method_lookup(
    g: Graph, cls_ast: ClassDef, m: str, v: VersionId
) -> VersionedMethod | None:
    if g.find_version(v) is None:
        return None
    interface = implementation = None
    # Start by looking for a local interface and implementation of `m`
    lm = __local_method_lookup(cls_ast, m, v)
    if lm is not None:
        interface = lm
        implementation = lm
    # If none is found, look for interface and implementation in parent versions
    else:
        um = __inherited_method_lookup(g, cls_ast, m, v)
        if um is not None:
            interface = um
            implementation = um
    # Finally, look for an implementation in replacement versions.
    try:
        rm = __replacement_method_lookup(g, cls_ast, m, v)
    # If there is a conflict in replacement versions, we still return the
    # local/parent definition, if we found one already. This is so that methods
    # defined @at(v) are still well typed. The conflict exception should be
    # handled at some other point, when checking the soundness of the entire
    # version graph against the class definition.
    except MethodConflictException as e:
        if implementation is None or interface is None:
            raise e
        rm = None
    if rm is not None:
        implementation = rm
        # If no interface was found yet, this means that method `m` was
        # introduced in a replacement version, so we set its interface to `rm`
        if interface is None:
            interface = rm

    if interface is not None and implementation is not None:
        return VersionedMethod(
            name=m, interface=interface, implementation=implementation
        )
    else:
        return None


def methods_at(cls_ast: ClassDef, v: VersionId) -> set[FunctionDef]:
    """
    Returns the methods of a class explicitly defined at version v.
    """

    visitor = MethodCollector(v=v)
    visitor.visit(cls_ast)
    return visitor.methods


def fields_at(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[Field]:
    """
    Returns the set of fields explicitly defined at version v.
    """
    methods = methods_at(cls_ast, v)
    visitor = ClassFieldCollector(cls_ast, [m.name for m in methods], v)
    for m in methods:
        visitor.visit(m)
    parent_fields = {f for p in g.parents(v) for f in fields_at(g, cls_ast, p.name)}
    result = set()
    # Iterate over fields at v and check if they are inherited or introduced here.
    for field, explicit in visitor.fields.items():
        if explicit:
            result.add(field)
        else:
            for pf in parent_fields:
                if field.name == pf.name:
                    # Found an inherited field
                    break
            else:
                # If no inherited field was found we add it to the result
                result.add(field)

    return result
