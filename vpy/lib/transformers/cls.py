from ast import (
    ClassDef,
    FunctionDef,
    NodeTransformer,
    Pass,
)
from vpy.lib import lookup
from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.transformers.assignment import AssignTransformer
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer
from vpy.lib.transformers.fields import FieldTransformer
from vpy.lib.transformers.rewrite import ExtractLocalVar
from vpy.lib.utils import (
    create_identity_lens,
    create_init,
    get_at,
    graph,
    is_lens,
)
from vpy.lib.visitors.alias import AliasVisitor


class ClassStrictTransformer(NodeTransformer):
    """
    Strict clice of a single class for a given version v.
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
        if lookup.base(g, node, self.v) is None:
            node.body.append(create_init(g=g, cls_ast=node, v=self.v))
            for w in g.parents(self.v):
                for field in lookup.fields_lookup(g, node, w):
                    id_lens_v_w = create_identity_lens(g, node, self.v, w, field)
                    self.env.get_lenses.put_lens(
                        v_from=self.v, field_name=field.name, v_to=w, lens=id_lens_v_w
                    )
                    node.body.append(id_lens_v_w)
                    id_lens_w_v = create_identity_lens(g, node, w, self.v, field)
                    self.env.get_lenses.put_lens(
                        v_from=w, field_name=field.name, v_to=self.v, lens=id_lens_w_v
                    )
                    node.body.append(id_lens_w_v)
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
        if (
            self.v_target == v_from
            or self.env.bases[self.v_target] == self.env.bases[v_from]
        ):
            return node
        # node = RemoveDecoratorsTransformer().visit(node)
        alias_visitor = AliasVisitor(
            g=self.g, cls_ast=self.cls_ast, env=self.env, v_from=v_from
        )
        alias_visitor.visit(node)
        fields_var = ExtractLocalVar(
            g=self.g,
            cls_ast=self.cls_ast,
            env=self.env,
            v_from=v_from,
            v_target=self.v_target,
            aliases=alias_visitor.aliases,
        )
        fields_var.visit(node)
        assign_rw = AssignTransformer(
            self.g, self.cls_ast, self.env, self.v_target, v_from
        )
        assign_rw.generic_visit(node)
        fields_rw = FieldTransformer(
            self.g,
            self.cls_ast,
            self.env,
            self.v_target,
            v_from,
        )
        fields_rw.generic_visit(node)
        # method_lens_rw = MethodLensTransformer(
        #     g=self.g,
        #     cls_ast=self.cls_ast,
        #     env=self.env,
        #     v_target=self.v_target,
        #     v_from=v_from,
        # )
        # method_lens_rw.visit(node)
        return node


class SelectMethodsStrictTransformer(NodeTransformer):
    """
    Selects the strict class methods for a given version v.
    """

    def __init__(self, v: VersionId):
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef | None:
        if is_lens(node):
            return None
        if get_at(node) == self.v:
            return node
        return None


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
