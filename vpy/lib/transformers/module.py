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
        fields = {}
        bases = {}
        for cls in node.body:
            if isinstance(cls, ClassDef):
                g = graph(cls)
                lenses = lookup.cls_lenses(g, cls)
                for k in g.all():
                    bases[k.name] = lookup.base(g, cls, k.name)
                    if cls.name not in fields:
                        fields[cls.name] = {}
                    fields[cls.name][k.name] = lookup.fields_lookup(g, cls, k.name)
                    for t in g.all():
                        if k != t:
                            if k.name not in lenses:
                                lenses[k.name] = defaultdict(dict)
                            if lens := lookup.lens_lookup(g, k.name, t.name, cls):
                                for field, lens_node in lens.items():
                                    lenses[k.name][field][t.name] = lens_node
        self.env = Environment(
            fields=fields, get_lenses=lenses, put_lenses=defaultdict(), bases=bases
        )
        self.generic_visit(node)
        node = ClassTransformer(v=self.v, env=self.env).visit(node)
        return node
