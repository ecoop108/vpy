from ast import (
    ClassDef,
    FunctionDef,
    NodeVisitor,
)

from vpy.lib.lib_types import VersionId
from vpy.lib.utils import get_at, is_lens


class MethodCollector(NodeVisitor):
    """
    Collects the methods explicitly defined at version `v`.
    """

    def __init__(self, v: VersionId):
        self.methods = set()
        self.v = v

    def visit_ClassDef(self, node: ClassDef):
        self.generic_visit(node)

    def visit_FunctionDef(self, node: FunctionDef):
        if not is_lens(node) and get_at(node) == self.v:
            self.methods.add(node)
