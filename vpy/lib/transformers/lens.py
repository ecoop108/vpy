from ast import Call, ClassDef, Name
from vpy.lib import lookup


from vpy.lib.lib_types import Field, VersionId
from vpy.lib.utils import (
    create_init,
    field_to_arg,
    fields_in_function,
    graph,
    set_typeof_node,
    typeof_node,
)
import ast


class PutLens(ast.NodeTransformer):
    """
    Synthesize put lens from the corresponding get lens.
    Replace all self fields in the lens with keyword-only arguments of the same name.
    """

    def __init__(self, fields: set[Field]):
        self.fields = fields
        self.__obj_arg: str | None = None

    def visit_FunctionDef(self, node):
        references = fields_in_function(node, self.fields)
        for field in references:
            node.args.kwonlyargs.append(field_to_arg(field))
            node.args.kw_defaults.append(None)
        # Replace the `get` decorator with `put`
        for dec in node.decorator_list:
            if (
                isinstance(dec, Call)
                and isinstance(dec.func, Name)
                and dec.func.id == "get"
            ):
                dec.func.id = "put"
        self.__obj_arg = node.args.args[0].arg
        self.generic_visit(node)
        self.__obj_arg = None
        return node

    def visit_Attribute(self, node):
        # Remove the object name (e.g. `self`) from the qualified attribute (`self.attr`) expression
        if isinstance(node.value, Name) and self.__obj_arg == node.value.id:
            name_node = Name(id=node.attr, ctx=ast.Load())
            set_typeof_node(name_node, typeof_node(node))
            node = name_node
        else:
            node.value = self.visit(node.value)
        return node
