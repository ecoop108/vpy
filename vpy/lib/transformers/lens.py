from ast import Call, ClassDef, Name
from vpy.lib import lookup


from vpy.lib.lib_types import Field, VersionId
from vpy.lib.utils import (
    create_identity_lens,
    create_init,
    field_to_arg,
    fields_in_function,
    graph,
    is_field,
)
import ast


class IdentityLens(ast.NodeTransformer):
    def __init__(self, v: VersionId):
        self.v = v

    def visit_ClassDef(self, node: ClassDef) -> ClassDef:
        g = graph(node)
        if lookup.base(g, node, self.v) is None:
            node.body.append(create_init(g=g, cls_ast=node, v=self.v))
            for w in g.parents(self.v):
                for field in lookup.fields_lookup(g, node, w):
                    node.body.append(create_identity_lens(g, node, self.v, w, field))
                    node.body.append(create_identity_lens(g, node, w, self.v, field))
        return node


class PutLens(ast.NodeTransformer):
    """
    Synthesize put lens from the corresponding get lens.
    Replace all self fields in the lens with arguments of the same name.
    """

    def __init__(self, fields: set[Field]):
        self.fields = fields

    def visit_FunctionDef(self, node):
        references = fields_in_function(node, self.fields)
        for field in references:
            node.args.kwonlyargs.append(field_to_arg(field))
            node.args.kw_defaults.append(None)
        for dec in node.decorator_list:
            if (
                isinstance(dec, Call)
                and isinstance(dec.func, Name)
                and dec.func.id == "get"
            ):
                dec.func.id = "put"
        # if node.returns is None:
        #     node.returns = Name(id=lens_field.type.simplify().__name__, ctx=Load())
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        # TODO: Fix this for nested fields
        if is_field(node, self.fields) and isinstance(node.ctx, ast.Load):
            name_node = Name(id=node.attr, ctx=ast.Load())
            name_node.inferred_value = [f for f in self.fields if f.name == node.attr][
                0
            ].type
            node = name_node
        else:
            node.value = self.visit(node.value)
        return node
