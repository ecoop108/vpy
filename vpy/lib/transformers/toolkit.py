from _ast import ClassDef
import ast
from typing import Any
from vpy.lib.lib_types import Version, VersionId


class AddVersionTransformer(ast.NodeTransformer):
    """
    Project a strict slice of a version.
    """

    def __init__(
        self, v: VersionId, replaces: list[VersionId], upgrades: list[VersionId]
    ):
        self.version = Version([])
        self.version.name = v
        self.version.upgrades = tuple(upgrades)
        self.version.replaces = tuple(replaces)

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ClassDef) -> Any:
        dec = ast.Call()
        dec.func = ast.Name(id="version", ctx=ast.Load())
        dec.keywords = [
            ast.keyword(arg="name", value=ast.Constant(value=self.version.name)),
            ast.keyword(
                arg="upgrades",
                value=ast.List(
                    elts=[ast.Constant(value=u) for u in self.version.upgrades]
                ),
            ),
            ast.keyword(
                arg="replaces",
                value=ast.List(
                    elts=[ast.Constant(value=r) for r in self.version.replaces]
                ),
            ),
        ]
        dec.args = []
        node.decorator_list.append(dec)
        self.generic_visit(node)
        return node
