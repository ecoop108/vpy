from ast import ClassDef, FunctionDef, NodeTransformer, Pass
from vpy.lib import lookup
from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.assignment import AssignTransformer
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer
from vpy.lib.transformers.fields import FieldTransformer
from vpy.lib.utils import get_at, graph, is_lens


class ClassTransformer(NodeTransformer):
    """
    Slice of a single class for a given version v.
    """

    def __init__(self, v: VersionId, env: Environment):
        self.v = v
        self.env = env

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        g = graph(node)
        node = SelectMethodsTransformer(g=g, v=self.v).visit(node)
        node = MethodTransformer(g=g, cls_ast=node, env=self.env, target=self.v).visit(
            node
        )
        node = RemoveDecoratorsTransformer().visit(node)
        node.name += "_" + self.v
        if node.body == []:
            node.body.append(Pass())
        return node


class MethodTransformer(NodeTransformer):
    """
    Rewrite method body for a given version v.
    """

    def __init__(
        self, g: Graph, cls_ast: ClassDef, env: Environment, target: VersionId
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_target = target

    def visit_FunctionDef(self, node):
        v_from = get_at(node)
        if self.v_target == v_from:
            return node
        assign_rw = AssignTransformer(
            self.g, self.cls_ast, self.env, self.v_target, v_from
        )
        fields_rw = FieldTransformer(
            self.g, self.cls_ast, self.env, self.v_target, v_from
        )
        assign_rw.generic_visit(node)
        fields_rw.generic_visit(node)
        return node


class SelectMethodsTransformer(NodeTransformer):
    """
    Selects the appropriate class methods for a given version v.
    """

    def __init__(self, g: Graph, v: VersionId):
        self.g = g
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        self.cls_ast = node
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef | None:
        if is_lens(node):
            return None
        methods = lookup.methods_lookup(self.g, self.cls_ast, self.v)
        if node not in methods:
            return None
        return node
