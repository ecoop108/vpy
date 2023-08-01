from ast import Call, Name, arg


from vpy.lib.lib_types import FieldName
from vpy.lib.utils import fields_in_function, is_field
import ast


class PutLens(ast.NodeTransformer):
    def __init__(self, fields: set[FieldName]):
        self.fields = fields

    def visit_FunctionDef(self, node):
        references = fields_in_function(node, self.fields)
        for f in references:
            node.args.kwonlyargs.append(arg(arg=f))
            node.args.kw_defaults.append(None)
        for dec in node.decorator_list:
            if (
                isinstance(dec, Call)
                and isinstance(dec.func, Name)
                and dec.func.id == "get"
            ):
                dec.func.id = "put"
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        # TODO: Fix this for nested fields
        if is_field(node, self.fields) and isinstance(node.ctx, ast.Load):
            node = Name(id=node.attr, ctx=ast.Load())
        else:
            node.value = self.visit(node.value)
        return node
