import ast
from ast import Attribute, ClassDef, FunctionDef

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import get_at


class MethodLensTransformer(ast.NodeTransformer):
    """
    Rewrite field access expressions of the form obj.field from version v_from to version v_target.
    """

    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        v_target: VersionId,
        v_from: VersionId,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_target = v_target
        self.v_from = v_from

    def visit_FunctionDef(self, node: FunctionDef):
        mver = get_at(node)
        method_lens = self.env.method_lenses.get_lens(
            self.env.bases[mver],
            v_to=self.env.bases[self.v_target],
            field_name=node.name,
        )
