import ast
from ast import FunctionDef, ClassDef
from typing import Callable, Optional, cast
import inspect
from vpy.lib.lib_types import Graph, VersionIdentifier
from vpy.lib.utils import is_lens, get_at


def lens_lookup(g: Graph, v: VersionIdentifier, t,
                cls) -> Optional[dict[str, tuple[ast.FunctionDef, Callable]]]:
    src = inspect.getsource(cls)
    cls_ast = cast(ClassDef, ast.parse(src).body[0])
    lenses = []
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            for dec in method.decorator_list:
                if dec.func.id == 'lens' and dec.args[
                        0].value == v and dec.args[1].value == t:
                    lenses.append((method, dec.args[2].value))
    if len(lenses) > 0:
        return {
            field: (node, getattr(cls, node.name))
            for node, field in lenses
        }
    return None


def methodsAt(g: Graph, cls_ast, v: VersionIdentifier) -> list[FunctionDef]:
    methods = [
        m for m in cls_ast.body if isinstance(m, ast.FunctionDef) and any([
            d.func.id == 'at' and d.args[0].value == v and (not is_lens(m))
            for d in m.decorator_list
        ])
    ]
    return methods


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
    methods = methodsAt(g, cls_ast, v)
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
        if isinstance(fun, ast.FunctionDef) and get_at(fun) == v:
            for stmt in ast.walk(fun):
                if isinstance(stmt, ast.Attribute) and isinstance(
                        stmt.value, ast.Name) and stmt.value.id == 'self':
                    found = True
    if found:
        return v
    for p in g[v].upgrades:
        back = base(g, cls_ast, p)
        if back is not None:
            return back
    return None


def fields_lookup(g, cls_ast: ClassDef, v: VersionIdentifier) -> set[str]:
    # local search
    fields = set()
    for node in ast.walk(cls_ast):
        if isinstance(node, ast.FunctionDef) and get_at(node) == base(
                g, cls_ast, v):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Attribute) and isinstance(
                        stmt.value, ast.Name) and stmt.value.id == 'self':
                    fields.add(stmt.attr)
    return fields
