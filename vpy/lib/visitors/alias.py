import ast
import copy
from ast import Assign, Attribute, Call, ClassDef, Expr, Name
from typing import Any

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    get_obj_attribute,
    has_get_lens,
    is_field,
    is_obj_attribute,
)


class AliasVisitor(ast.NodeVisitor):
    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        v_from: VersionId,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_from = v_from
        self.aliases = {}

    def visit_Assign(self, node: Assign) -> Any:
        if isinstance(node.value, Attribute) and is_obj_attribute(node.value):
            if is_field(
                node.value,
                self.env.fields[node.value.value.inferred_value.get_type().__name__][
                    self.v_from
                ],
            ):
                # TODO: Case where we have multiple targets or tuple value?
                self.aliases[node.targets[0]] = (
                    node.value.value.inferred_value.get_type().__name__,
                    node.value,
                )

    # TODO: Is this needed?
    # def visit_Attribute(self, node):
    #     pass

    def visit_Name(self, node: Name) -> Any:
        existing = [
            n for n in self.aliases.keys() if isinstance(n, Name) and n.id == node.id
        ]
        if existing:
            existing_node = existing[-1]
            self.aliases[node] = self.aliases[existing_node]
