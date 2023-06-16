import ast
from ast import Attribute, ClassDef, FunctionDef, NodeVisitor
from typing import Optional
from vpy.lib.lib_types import Graph, Lenses, VersionId
from vpy.lib.utils import get_decorator, is_lens, get_at, is_obj_attribute


def path_lookup(g: Graph, v: VersionId, t: VersionId,
                lenses: Lenses) -> list[tuple[VersionId, VersionId]] | None:
    lens = lenses[v]
    if t in lens and lens[t] is not None:
        return [(v, t)]
    for w in lens:
        if (p := path_lookup(g.delete(v), w, t, lenses)) is not None:
            return [(v, w)] + p
    return None


def cls_lenses(g: Graph, cls_ast: ClassDef) -> Lenses:
    lenses: Lenses = {}
    for k in g.all():
        for t in g.all():
            if k != t:
                base_k, _ = base(g, cls_ast, k.name)
                base_t, _ = base(g, cls_ast, t.name)
                if base_k not in lenses:
                    lenses[base_k] = {}
                if (lens := lens_lookup(g, k.name, t.name,
                                        cls_ast)) is not None:
                    lenses[base_k][base_t] = lens
    return lenses


def lenses_at(cls_ast: ClassDef,
              v: VersionId) -> dict[VersionId, dict[str, FunctionDef]]:
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
                    if target not in lenses:
                        lenses[target] = {}
                    lenses[target][field] = method
    return lenses


def lens_lookup(g: Graph, v: VersionId, t: VersionId,
                cls_ast: ClassDef) -> dict[str, FunctionDef] | None:
    lenses = lenses_at(cls_ast=cls_ast, v=v)
    if t in lenses:
        return lenses[t]
    base_t, _ = base(g, cls_ast, t)
    if base_t in lenses:
        return lenses[base_t]
    return None


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
    um = [
        me for me in
        [method_lookup(g.delete(v), cls_ast, m, r) for r in g.parents(v)]
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


def base(g: Graph, cls_ast: ClassDef,
         v: VersionId) -> tuple[VersionId, set[str]]:

    class FieldCollector(ast.NodeVisitor):

        def __init__(self):
            self.references = set()
            self.methods = [
                m.name for m in methods_at(g, cls_ast, v)
                if _replacement_method_lookup(g, cls_ast, m.name, v) is None
            ]
            self.fields = set()

        def visit_FunctionDef(self, node: FunctionDef):
            if get_at(node) != v:
                return
            self.self_param = node.args.args[0].arg
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, Attribute) and is_obj_attribute(
                        target, self.self_param):
                    if target.attr not in self.methods:
                        self.fields.add(target.attr)

        def visit_AnnAssign(self, node):
            if isinstance(node.target, Attribute) and is_obj_attribute(
                    node.target, self.self_param):
                if node.target.attr not in self.methods:
                    self.fields.add(node.target.attr)

        def visit_AugAssign(self, node):
            if isinstance(node.target, Attribute) and is_obj_attribute(
                    node.target, self.self_param):
                if node.target.attr not in self.methods:
                    self.fields.add(node.target.attr)

    visitor = FieldCollector()
    visitor.visit(cls_ast)
    inherited = set()
    for p in g.parents(v):
        _, fields = base(g.delete(v), cls_ast, p)
        for field in fields:
            inherited.add(field)

    if len(visitor.fields) > 0 and any(field not in inherited
                                       for field in visitor.fields):
        return (v, visitor.fields)
    for p in g.parents(v):
        back = base(g, cls_ast, p)
        if back is not None:
            return back
    return None


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
