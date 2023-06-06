import ast
from ast import FunctionDef, ClassDef
from typing import Optional
from vpy.lib.lib_types import Graph, VersionIdentifier
from vpy.lib.utils import is_lens, get_at, is_self_attribute


def __lens_lookup(
        cls_ast: ClassDef, v: VersionIdentifier
) -> dict[VersionIdentifier, dict[str, FunctionDef]]:
    lenses = {}
    for method in cls_ast.body:
        if isinstance(method, FunctionDef):
            for dec in method.decorator_list:
                if isinstance(dec, ast.Call):
                    if isinstance(
                            dec.func, ast.Name
                    ) and dec.func.id == 'get' and dec.args[0].value == v:
                        target = dec.args[1].value
                        field = dec.args[2].value
                        if target not in lenses:
                            lenses[target] = {}
                        lenses[target][field] = method
    return lenses


def lens_at(g: Graph, v: VersionIdentifier, t: VersionIdentifier,
            cls_ast: ClassDef) -> Optional[dict[str, FunctionDef]]:
    lens = __lens_lookup(cls_ast=cls_ast, v=v)
    if t in lens:
        return lens[t]
    return None


def __replacement_method_lookup(g: Graph, cls_ast: ClassDef, m,
                                v: VersionIdentifier) -> Optional[FunctionDef]:
    replacements = g.replacements(v)
    rm = [
        me for me in
        [method_lookup(g.delete(v), cls_ast, m, r.name) for r in replacements]
        if me is not None and m != '__init__'
    ]
    return rm[0] if len(rm) == 1 else None


def __local_method_lookup(cls_ast: ClassDef, m,
                          v: VersionIdentifier) -> Optional[FunctionDef]:
    methods = [
        m for m in cls_ast.body
        if isinstance(m, ast.FunctionDef) and not is_lens(m) and get_at(m) == v
    ]
    lm = [
        me for me in [me for me in methods if me.name == m] if me is not None
    ]
    return lm[0] if len(lm) == 1 else None


def __inherited_method_lookup(g: Graph, cls_ast: ClassDef, m,
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
                  v: VersionIdentifier) -> FunctionDef | None:
    if v not in g:
        return None

    # replacement search
    rm = __replacement_method_lookup(g, cls_ast, m, v)
    if rm is not None:
        return rm

    # local search
    lm = __local_method_lookup(cls_ast, m, v)
    if lm is not None:
        return lm

    # upgrade search
    um = __inherited_method_lookup(g, cls_ast, m, v)
    if um is not None:
        return um
    return None


#TODO: Fix this. Should only look for fields.
def base(g, cls_ast: ClassDef,
         v: VersionIdentifier) -> Optional[VersionIdentifier]:
    # class BaseVisitor(ast.NodeVisitor):
    #     def __init__(self):
    #         pass
    #     def visit_FunctionDef(self, node: FunctionDef):
    #         if is_lens(node):
    #             return
    #         if get_at(node) != v:
    #             return

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


def methods_at(g: Graph, cls_ast: ClassDef,
               v: VersionIdentifier) -> set[FunctionDef]:
    """
    Returns the methods of class cls available at version v.
    """

    class MethodCollector(ast.NodeVisitor):

        def __init__(self):
            self.methods = set()

        def visit_ClassDef(self, node: ClassDef):
            for expr in node.body:
                if isinstance(expr, FunctionDef):
                    mdef = method_lookup(g, cls_ast, node.name, v)
                    if mdef is not None:
                        self.methods.add(mdef)

    visitor = MethodCollector()
    visitor.visit(cls_ast)
    return visitor.methods


def fields_at(g, cls: ClassDef, v: VersionIdentifier) -> set[str]:
    """
    Returns the field names defined in class cls for version v.
    """

    class FieldCollector(ast.NodeVisitor):

        def __init__(self):
            self.references = set()
            self.methods = [m.name for m in methods_at(g, cls, v)]
            self.base = base(g, cls, v)
            self.fields = set()

        def visit_FunctionDef(self, node: FunctionDef):
            # if is_lens(node):
            #     return
            if get_at(node) != self.base:
                return
            for stmt in node.body:
                self.visit(stmt)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target,
                              ast.Attribute) and is_self_attribute(target):
                    if target.attr not in self.methods:
                        self.fields.add(target.attr)

        def visit_AnnAssign(self, node: ast.AnnAssign):
            if isinstance(node.target, ast.Attribute) and is_self_attribute(
                    node.target):
                if node.target.attr not in self.methods:
                    self.fields.add(node.target.attr)

        def visit_AugAssign(self, node: ast.AugAssign):
            if isinstance(node.target, ast.Attribute) and is_self_attribute(
                    node.target):
                if node.target.attr not in self.methods:
                    self.fields.add(node.target.attr)

    visitor = FieldCollector()
    visitor.visit(cls)
    return visitor.fields
