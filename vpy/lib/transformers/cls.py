from ast import (
    ClassDef,
    FunctionDef,
    NodeTransformer,
    Pass,
)
from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.assignment import AssignTransformer
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer
from vpy.lib.transformers.fields import FieldTransformer
from vpy.lib.transformers.methods import MethodLensTransformer
from vpy.lib.transformers.rewrite import ExtractLocalVar
from vpy.lib.utils import (
    get_at,
    graph,
    is_lens,
)
from vpy.lib.visitors.alias import AliasVisitor


class ClassStrictTransformer(NodeTransformer):
    """
    Strict slice of a single class for a given version v.
    Select methods and fields explcitily defined at version v.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        node = SelectMethodsStrictTransformer(v=self.v).visit(node)
        node = RemoveDecoratorsTransformer().visit(node)
        node.name += "_" + self.v
        if node.body == []:
            node.body.append(Pass())
        return node


class ClassTransformer(NodeTransformer):
    """
    Slice of a single class for a given version v.
    """

    def __init__(self, v: VersionId, env: Environment):
        self.v = v
        self.env = env

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        g = graph(node)
        node = SelectMethodsTransformer(
            g=g, v=self.v, cls_ast=node, env=self.env
        ).visit(node)
        node = MethodTransformer(g=g, cls_ast=node, env=self.env, target=self.v).visit(
            node
        )
        node = RemoveDecoratorsTransformer().visit(node)
        if node.body == []:
            node.body.append(Pass())
        return node


class MethodTransformer(NodeTransformer):
    """
    Transformer to rewrite method body for a given version v.
    """

    def __init__(
        self, g: Graph, cls_ast: ClassDef, env: Environment, target: VersionId
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_target = target

    def visit_FunctionDef(self, node: FunctionDef):
        v_from = get_at(node)
        if self.v_target == v_from:
            return node
        if all(
            vb not in self.env.bases[self.cls_ast.name][self.v_target]
            for vb in self.env.bases[self.cls_ast.name][v_from]
        ):
            alias_visitor = AliasVisitor(
                g=self.g, cls_ast=self.cls_ast, env=self.env, v_from=v_from
            )
            fields_var = ExtractLocalVar(
                g=self.g,
                cls_ast=self.cls_ast,
                env=self.env,
                v_from=v_from,
                v_target=self.v_target,
                aliases=alias_visitor.aliases,
            )
            assign_rw = AssignTransformer(
                self.g,
                self.cls_ast,
                self.env,
                self.v_target,
                v_from,
            )
            alias_visitor.visit(node)
            fields_var.visit(node)
            assign_rw.generic_visit(node)
            fields_rw = FieldTransformer(
                self.g,
                self.cls_ast,
                self.env,
                self.v_target,
                v_from,
            )
            fields_rw.generic_visit(node)
        method_lens_rw = MethodLensTransformer(
            g=self.g,
            cls_ast=self.cls_ast,
            env=self.env,
            v_target=self.v_target,
            v_from=v_from,
        )
        node = method_lens_rw.visit(node)
        return node


class SelectMethodsStrictTransformer(NodeTransformer):
    """
    Selects the strict class methods for a given version v.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef | None:
        if is_lens(node):
            return None
        if get_at(node) == self.v:
            return node
        return None


class SelectMethodsTransformer(NodeTransformer):
    """
    Selects the class methods for version v.
    """

    def __init__(self, g: Graph, v: VersionId, cls_ast: ClassDef, env: Environment):
        self.g = g
        self.v = v
        self.env = env
        self.cls_ast = cls_ast

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef | None:
        if all(
            node != m.implementation
            for m in self.env.methods[self.cls_ast.name][self.v]
        ):
            return None
        return node
