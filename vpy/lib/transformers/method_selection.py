import ast
from ast import ClassDef, FunctionDef

import vpy.lib.lookup as lookup
from vpy.lib.lib_types import Graph, VersionId
from vpy.lib.utils import get_at, is_lens


class SelectMethodsTransformer(ast.NodeTransformer):

    def __init__(self, g: Graph, v: VersionId):
        self.g = g
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        self.cls_node = node
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef | None:
        if is_lens(node):
            return None
        mdef = lookup.method_lookup(self.g, self.cls_node, node.name, self.v)
        if mdef is None or get_at(mdef) != get_at(node):
            return None
        return node
