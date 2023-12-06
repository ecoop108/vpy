import ast
from ast import ClassDef
from collections import defaultdict

from vpy.lib import lookup
from vpy.lib.lib_types import Environment, Lenses, VersionId
from vpy.lib.transformers.cls import ClassStrictTransformer, ClassTransformer
from vpy.lib.utils import graph
from vpy.typechecker.checker import check_cls, check_module


class ModuleStrictTransformer(ast.NodeTransformer):
    """
    Project a strict slice of a version.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_Module(self, node):
        node = ClassStrictTransformer(v=self.v).visit(node)
        return node


class ModuleTransformer(ast.NodeTransformer):
    """
    Rewrite all classes in a module.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_Module(self, node):
        for idx, cls in enumerate(node.body):
            if isinstance(cls, ClassDef):
                fields = {}
                bases = {}
                g = graph(cls)
                for k in g.all():
                    bases[k.name] = lookup.base(g, cls, k.name)
                    if cls.name not in fields:
                        fields[cls.name] = {}
                    fields[cls.name][k.name] = lookup.fields_lookup(g, cls, k.name)
                self.env = Environment(
                    fields=fields,
                    get_lenses=lookup.field_lenses_lookup(g, cls),
                    put_lenses=Lenses(),
                    method_lenses=lookup.method_lenses_lookup(g, cls),
                    bases=bases,
                )
                node.body[idx] = ClassTransformer(v=self.v, env=self.env).visit(cls)
        return node
