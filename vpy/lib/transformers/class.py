from typing import Type
from vpy.lib.lib_types import VersionIdentifier
from ast import ClassDef
from vpy.lib.utils import parse_class, is_lens, get_at
import vpy.lib.lookup as lookup
import copy
import ast


def tr_class(mod, cls: Type, v: VersionIdentifier) -> ClassDef:
    cls_ast, g = parse_class(cls)
    tr_cls_ast = copy.deepcopy(cls_ast)

    class ClassTransformer(ast.NodeTransformer):
        """
        Takes an AST node of a class and selects only methods for version `v`.
        Each method is rewritten to match the context of `v` if needed.
        """
        parent = tr_cls_ast

        def visit_ClassDef(self, node: ClassDef):
            self.parent = node
            for expr in list(node.body):
                expr = self.visit(expr)
            return node

        def visit_FunctionDef(self, node):
            if is_lens(node):
                return node
            mdef = lookup.method_lookup(g, cls_ast, node.name, v)
            if mdef is None:
                assert (False)
            target = get_at(mdef)
            if bases[target] == bases[v]:
                return node
            lenses = lookup.lens_at(g, target, v, cls_ast)
            if lenses is not None:
                node = tr_lens(cls_ast, self.parent, node, g, v, target)
            else:
                assert False
            return node

    bases = {}
    fields = {}
    for v in g.keys():
        base = lookup.base(g, cls_ast, v)
        if base is not None:
            bases[v], fields[v] = base
    tr_cls_ast = tr_select_methods(g, tr_cls_ast, v)
    # tr_cls_ast = tr_put_lens(tr_cls_ast)
    ClassTransformer().visit(tr_cls_ast)
    tr_cls_ast.name += '_' + v
    if tr_cls_ast.body == []:
        tr_cls_ast.body.append(ast.Pass())
    return remove_decorators(tr_cls_ast)
