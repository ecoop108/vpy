import ast
from ast import Attribute, ClassDef, FunctionDef, NodeVisitor
from vpy.lib.lib_types import FieldName, Graph, Lenses, VersionId
from vpy.lib.utils import FieldReferenceCollector, get_decorator, get_self_obj, is_lens, get_at, is_obj_attribute
from collections import defaultdict


def cls_lenses(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses: Lenses = defaultdict(
        lambda: defaultdict(lambda: defaultdict(FunctionDef)))
    for k in g.all():
        for t in g.all():
            if k != t:
                if (lens := lens_lookup(g, k.name, t.name, cls_ast)):
                    for field, lens_node in lens.items():
                        lenses[k.name][field][t.name] = lens_node
    return lenses


def lenses_to(g: Graph, cls_ast: ClassDef,
              v: VersionId) -> dict[str, dict[VersionId, FunctionDef]]:
    """
    Returns the lenses explicitly defined at version v.
    """
    lenses = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            decorator = get_decorator(method, 'get')
            if decorator:
                at, target, field = [
                    a.value for a in decorator.args
                    if isinstance(a, ast.Constant)
                ]
                if target == v and g.find_version(
                        at) is not None and g.find_version(target) is not None:
                    if field not in lenses:
                        lenses[field] = {}
                    lenses[field][at] = method
    return lenses


def lenses_at(cls_ast: ClassDef,
              v: VersionId) -> dict[str, dict[VersionId, FunctionDef]]:
    """
    Returns the lenses explicitly defined at version v.
    """
    lenses = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            decorator = get_decorator(method, 'get')
            if decorator:
                at, target, field = [
                    a.value for a in decorator.args
                    if isinstance(a, ast.Constant)
                ]
                if at == v:
                    if field not in lenses:
                        lenses[field] = {}
                    lenses[field][target] = method
    return lenses


def field_lens_lookup(g: Graph, v: VersionId, t: VersionId, cls_ast: ClassDef,
                      field: str) -> list[dict[str, FunctionDef]] | None:
    """
    Returns a list of lenses to rewrite field from version v to version t
    """
    lenses = lenses_to(g=g, cls_ast=cls_ast, v=v)
    if field not in lenses:
        return None
    if t in lenses[field]:
        return [{field: lenses[field][t]}]
    else:
        for w, lens in lenses[field].items():
            result = [{field: lens}]
            _, fields_w = fields_lookup(g, cls_ast, w)
            visitor = FieldReferenceCollector(None, fields_w)
            visitor.visit(lens)
            for ref in visitor.references:
                path = field_lens_lookup(g.delete(v), w, t, cls_ast, ref)
                if path is None:
                    break
                result += path
            else:
                return result
        return None


def lens_lookup(g: Graph, v: VersionId, t: VersionId,
                cls_ast: ClassDef) -> dict[FieldName, FunctionDef]:
    """
    Returns the lenses from v to t.
    """
    _, fields_v = fields_lookup(g, cls_ast, v)
    result: dict[FieldName, FunctionDef] = {}
    for field in fields_v:
        path = field_lens_lookup(g, v, t, cls_ast, field)
        if path is not None:
            lens = path[0][field]
            result[field] = lens
    return result


def _replacement_method_lookup(g: Graph, cls_ast: ClassDef, m: str,
                               v: VersionId) -> FunctionDef | None:
    replacements = g.replacements(v)
    rm = [
        me for me in
        [method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements]
        if me is not None and m != '__init__'
    ]
    return rm[0] if len(rm) == 1 else None


def _local_method_lookup(cls_ast: ClassDef, m: str,
                         v: VersionId) -> FunctionDef | None:
    methods = [
        m for m in cls_ast.body
        if isinstance(m, ast.FunctionDef) and not is_lens(m) and get_at(m) == v
    ]
    lm = [
        me for me in [me for me in methods if me.name == m] if me is not None
    ]
    return lm[0] if len(lm) == 1 else None


def _inherited_method_lookup(g: Graph, cls_ast: ClassDef, m: str,
                             v: VersionId) -> FunctionDef | None:
    graph = g.delete(v)
    um = [
        me
        for me in [method_lookup(graph, cls_ast, m, r) for r in g.parents(v)]
        if me is not None
    ]
    return um[0] if len(um) == 1 else None


def method_lookup(g: Graph, cls_ast: ClassDef, m: str,
                  v: VersionId) -> FunctionDef | None:
    if g.find_version(v) is None:
        return None
    rm = _replacement_method_lookup(g, cls_ast, m, v)
    if rm is not None:
        return rm

    lm = _local_method_lookup(cls_ast, m, v)
    if lm is not None:
        return lm

    um = _inherited_method_lookup(g, cls_ast, m, v)
    if um is not None:
        return um
    return None


def fields_lookup(g: Graph, cls_ast: ClassDef,
         v: VersionId) -> tuple[VersionId, set[FieldName]]:

    class FieldCollector(ast.NodeVisitor):

        def __init__(self):
            self.references = set()
            self.methods = [
                m.name for m in methods_at(g, cls_ast, v)
                if _replacement_method_lookup(g, cls_ast, m.name, v) is None
            ]
            self.fields: set[FieldName] = set()

        def visit_FunctionDef(self, node: FunctionDef):
            if get_at(node) != v:
                return
            self.self_param = node.args.args[0].arg
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, Attribute) and is_obj_attribute(target):
                    if target.attr not in self.methods:
                        self.fields.add(FieldName(target.attr))

        def visit_AnnAssign(self, node):
            if isinstance(node.target, Attribute) and is_obj_attribute(
                    node.target):
                if node.target.attr not in self.methods:
                    self.fields.add(FieldName(node.target.attr))

        def visit_AugAssign(self, node):
            if isinstance(node.target, Attribute) and is_obj_attribute(
                    node.target):
                if node.target.attr not in self.methods:
                    self.fields.add(FieldName(node.target.attr))

    visitor = FieldCollector()
    visitor.visit(cls_ast)
    inherited = set()
    for p in g.parents(v):
        _, fields = fields_lookup(g.delete(v), cls_ast, p)
        for field in fields:
            inherited.add(field)

    if len(visitor.fields) > 0 and any(field not in inherited
                                       for field in visitor.fields):
        return (v, visitor.fields)
    for p in g.parents(v):
        back = fields_lookup(g, cls_ast, p)
        if back is not None:
            return back
    return (v, set())


def methods_at(g: Graph, cls_ast: ClassDef, v: VersionId) -> set[FunctionDef]:
    """
    Returns the methods of class cls available at version v.
    """

    class MethodCollector(NodeVisitor):

        def __init__(self):
            self.methods = set()

        def visit_ClassDef(self, node: ClassDef):
            for expr in node.body:
                if isinstance(expr, FunctionDef):
                    mdef = method_lookup(g, cls_ast, expr.name, v)
                    if mdef is not None and get_at(expr) == get_at(mdef):
                        self.methods.add(mdef)

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods
