import ast
from ast import ClassDef
from collections import defaultdict

from vpy.lib import lookup
from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer
from vpy.lib.transformers.lens import MethodRewriteTransformer
from vpy.lib.transformers.method_selection import SelectMethodsTransformer
from vpy.lib.utils import graph


class ModuleTransformer(ast.NodeTransformer):

    def __init__(self, v: VersionId):
        self.v = v

    def visit_Module(self, node):
        self.generic_visit(node)
        node = RemoveDecoratorsTransformer().visit(node)
        return node

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        g = graph(node)
        fields = {}
        lenses = lookup.cls_lenses(g, node)
        for k in g.all():
            fields[k.name] = lookup.fields_lookup(g, node, k.name)[1]
            for t in g.all():
                if k != t:
                    if k.name not in lenses:
                        lenses[k.name] = defaultdict(dict)
                    if (lens := lookup.lens_lookup(g, k.name, t.name, node)):
                        for field, lens_node in lens.items():
                            lenses[k.name][field][t.name] = lens_node
        node = SelectMethodsTransformer(g=g, v=self.v).visit(node)
        node = MethodRewriteTransformer(g=g,
                                        cls_ast=node,
                                        fields=fields,
                                        get_lenses=lenses,
                                        target=self.v).visit(node)
        node.name += '_' + self.v
        if node.body == []:
            node.body.append(ast.Pass())
        return node
