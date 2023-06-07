import ast
from ast import ClassDef, FunctionDef

import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Graph, VersionIdentifier
from vpy.lib.utils import get_at, is_lens


class SelectMethodsTransformer(ast.NodeTransformer):

    def __init__(self, g: Graph, v: VersionIdentifier):
        self.g = g
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        for expr in list(node.body):
            if not isinstance(expr, FunctionDef):
                continue
            if is_lens(expr):
                node.body.remove(expr)
                continue
            mdef = lookup.method_lookup(self.g, node, expr.name, self.v)
            if mdef is None or get_at(mdef) != get_at(expr):
                node.body.remove(expr)
        return node
