import ast
from ast import FunctionDef, ClassDef
from typing import Optional
from vpy.lib.lib_types import Graph, Lens, VersionIdentifier
from vpy.lib.utils import is_lens, get_at


def lens_at(cls_ast: ClassDef,
            v: VersionIdentifier) -> dict[VersionIdentifier, dict[str, Lens]]:
    lenses = {}
    lenses_get = {}
    lenses_put = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            for dec in method.decorator_list:
                if dec.func.id == 'get' and dec.args[0].value == v:
                    lenses_get[(dec.args[1].value, dec.args[2].value)] = method
                if dec.func.id == 'put' and dec.args[0].value == v:
                    lenses_put[(dec.args[1].value, dec.args[2].value)] = method
    for ((target, field), method) in lenses_get.items():
        if target not in lenses:
            lenses[target] = {}
        lenses[target][field] = Lens(put=lenses_put.get((target, field), None),
                                     get=method)
    return lenses


def lens_lookup(g: Graph, v: VersionIdentifier, t: VersionIdentifier,
                cls_ast: ClassDef) -> Optional[dict[str, Lens]]:
    lens = lens_at(cls_ast=cls_ast, v=v)
    if t in lens:
        return lens[t]
    return None


def methodsAt(g: Graph, cls_ast, v: VersionIdentifier) -> list[FunctionDef]:
    return [
        m for m in cls_ast.body if isinstance(m, ast.FunctionDef) and any([
            d.func.id == 'at' and d.args[0].value == v and (not is_lens(m))
            for d in m.decorator_list
        ])
    ]


def replacement_method_lookup(g: Graph, cls_ast: ClassDef, m,
                              v: VersionIdentifier) -> Optional[FunctionDef]:
    replacements = g.replacements(v)
    rm = [
        me for me in
        [method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements]
        if me is not None and m != '__init__'
    ]
    return rm[0] if len(rm) == 1 else None


def local_method_lookup(g: Graph, cls_ast: ClassDef, m,
                        v: VersionIdentifier) -> Optional[FunctionDef]:
    methods = methodsAt(g, cls_ast, v)
    lm = [
        me for me in [me for me in methods if me.name == m] if me is not None
    ]
    return lm[0] if len(lm) == 1 else None


def inherited_method_lookup(g: Graph, cls_ast: ClassDef, m,
                            v: VersionIdentifier) -> Optional[FunctionDef]:
    version = g[v]
    um = [
        me for me in [
            method_lookup(g.delete(v), cls_ast, m, r)
            for r in version.upgrades + version.replaces
        ] if me is not None
    ]
    return um[0] if len(um) == 1 else None


def method_lookup(g: Graph, cls_ast: ClassDef, m,
                  v: VersionIdentifier) -> Optional[FunctionDef]:
    if v not in g:
        return None

    # replacement search
    rm = replacement_method_lookup(g, cls_ast, m, v)
    if rm is not None:
        return rm

    # local search
    lm = local_method_lookup(g, cls_ast, m, v)
    if lm is not None:
        return lm

    # upgrade search
    um = inherited_method_lookup(g, cls_ast, m, v)
    if um is not None:
        return um
    return None


def base(g, cls_ast: ClassDef,
         v: VersionIdentifier) -> Optional[VersionIdentifier]:
    found = False
    for fun in ast.walk(cls_ast):
        if isinstance(
                fun,
                ast.FunctionDef) and (not is_lens(fun)) and get_at(fun) == v:
            for stmt in ast.walk(fun):
                if isinstance(stmt, ast.Attribute) and isinstance(
                        stmt.value, ast.Name) and stmt.value.id == 'self':
                    found = True
    if found:
        return v
    for p in (g[v].upgrades + g[v].replaces):
        back = base(g, cls_ast, p)
        if back is not None:
            return back
    return None


def fields_lookup(g, cls_ast: ClassDef, v: VersionIdentifier) -> set[str]:
    # local search
    fields = set()
    for node in ast.walk(cls_ast):
        if isinstance(node, ast.FunctionDef) and (
                not is_lens(node)) and get_at(node) == base(g, cls_ast, v):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Attribute) and isinstance(
                        stmt.value, ast.Name) and stmt.value.id == 'self':
                    fields.add(stmt.attr)
    return fields
