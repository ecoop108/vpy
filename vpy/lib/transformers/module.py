import ast
from ast import ClassDef, Module
from collections import defaultdict

from vpy.lib import lookup
from vpy.lib.lib_types import Environment, Lenses, VersionId
from vpy.lib.transformers.cls import ClassStrictTransformer, ClassTransformer
from vpy.lib.utils import get_module_environment, graph


class ModuleStrictTransformer(ast.NodeTransformer):
    """
    Strict projection of a version of this module.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_Module(self, node: Module):
        node = ClassStrictTransformer(v=self.v).visit(node)
        return node


class ModuleTransformer(ast.NodeTransformer):
    """
    Project a version of this module.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_Module(self, node: Module):
        env = get_module_environment(node)
        node = ClassTransformer(v=self.v, env=env).visit(node)
        return node
