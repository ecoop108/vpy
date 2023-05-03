import ast
from typing import Callable, Optional
import inspect
from lib_types import Graph, Version


def method_all_lookup(cls_ast):
    return set([
        e.name for e in cls_ast.body
        if isinstance(e, ast.FunctionDef) and all(d.func.id != 'lens'
                                                  for d in e.decorator_list)
    ])


def lens_lookup(g, v, t, cls) -> Optional[tuple[ast.FunctionDef, Callable]]:
    src = inspect.getsource(cls)
    cls_ast = ast.parse(src).body[0]
    cl_lenses = [
        m for m in cls_ast.body for d in m.decorator_list if
        d.func.id == 'lens' and d.args[0].value == v and d.args[1].value == t
        if isinstance(m, ast.FunctionDef)
    ]
    if cl_lenses:
        node = cl_lenses[0]
        return (node, getattr(cls, node.name))
    return (None, None)


def replacement_lookup(g: Graph, v: str) -> list[Version]:
    replacements = []
    version = g[v]
    for el in g.values():
        if version.name in el.replaces:
            replacements.append(el)
    return replacements


def methodsAt(g: Graph, cls_ast, v):
    methods = [
        m for m in cls_ast.body if isinstance(m, ast.FunctionDef) and any([
            d.func.id == 'at' and d.args[0].value == v
            for d in m.decorator_list
        ])
    ]
    return methods


def method_lookup(g, cls_ast, m, v: str):
    version = g[v]

    # replacement search
    replacements = replacement_lookup(g, v)
    rm = [
        me for me in
        [method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements]
        if me is not None and m != '__init__'
    ]
    if len(rm) == 1:
        return rm[0]

    # local search
    methods = methodsAt(g, cls_ast, v)
    lm = [
        me for me in [me for me in methods if me.name == m] if me is not None
    ]
    if len(lm) == 1:
        return lm[0]

    # upgrade search
    um = [
        me
        for me in [method_lookup(g, cls_ast, m, r) for r in version.upgrades]
        if me is not None
    ]
    if len(um) == 1:
        return um[0]
    return None


def fields_lookup(g, cls_ast, v):
    # local search
    fields = []
    init = method_lookup(g, cls_ast, '__init__', v)
    for expr in init.body:
        if isinstance(expr, ast.Assign):
            if isinstance(expr.targets[0], ast.Attribute):
                if expr.targets[0].value.id == 'self':
                    fields.append(expr.targets[0].attr)
    return fields
