from ast import (
    AnnAssign,
    Assign,
    Attribute,
    AugAssign,
    ClassDef,
    Constant,
    Del,
    FunctionDef,
    Load,
    Name,
    NodeVisitor,
    Store,
)
from typing import Type

from vpy.lib.lib_types import Field, FieldReference, VersionId
from vpy.lib.utils import get_at, typeof_node, is_field
from vpy.typechecker.pyanalyze.value import AnySource, AnyValue, TypedValue


class ClassFieldCollector(NodeVisitor):
    """
    Collects the fields explicitly defined in a class at version v. The collection is a dict[f: Field => i:bool] where
    `f` is the `Field` object and `i` is a boolean indicating whether this field is defined in `__init__` or not.
    """

    def __init__(self, cls_methods: list[str], v: VersionId):
        self.__cls_methods = cls_methods
        self.__v = v
        self.__in_constructor = False
        self.fields: dict[Field, bool] = dict()

    def visit_ClassDef(self, node: ClassDef):
        assert False

    def visit_FunctionDef(self, node: FunctionDef):
        # Only look in methods defined at version v.
        try:
            if get_at(node) != self.__v:
                return None
        # Case where we are in a nested function
        except AssertionError:
            pass
        self.__in_constructor: bool = node.name == "__init__"
        self.__caller_attr: str | None
        if len(node.args.args) > 0:
            self.__caller_attr = node.args.args[0].arg
        else:
            self.__caller_attr = None
        self.generic_visit(node)

    def visit_Assign(self, node: Assign):
        for target in node.targets:
            if isinstance(target, Attribute):
                if (
                    isinstance(target.value, Name)
                    and (target.value.id == self.__caller_attr)
                    and target.attr not in self.__cls_methods
                ):
                    self.__add_field(Field(name=target.attr, type=typeof_node(target)))

    def visit_AnnAssign(self, node: AnnAssign):
        if (
            isinstance(node.target, Attribute)
            and (isinstance(node.target.value, Name))
            and (node.target.value.id == self.__caller_attr)
            and (node.target.attr not in self.__cls_methods)
        ):
            field_type = AnyValue(AnySource(AnySource.default))
            if isinstance(node.annotation, Name):
                field_type = TypedValue(node.annotation.id)
            elif isinstance(node.annotation, Constant):
                field_type = TypedValue(node.annotation.value)
            self.__add_field(Field(node.target.attr, type=field_type))

    def visit_AugAssign(self, node: AugAssign):
        if (
            isinstance(node.target, Attribute)
            and (isinstance(node.target.value, Name))
            and (node.target.value.id == self.__caller_attr)
            and (node.target.attr not in self.__cls_methods)
        ):
            self.__add_field(
                Field(name=node.target.attr, type=typeof_node(node.target))
            )

    def __add_field(self, field: Field):
        if self.__in_constructor:
            self.fields[field] = True
        elif field not in self.fields:
            self.fields[field] = False


class FieldNodeCollector(NodeVisitor):
    """
    Collect all field reference nodes in a class
    """

    def __init__(self, fields: set[Field], *, ctx=(Load, Store, Del)):
        self.fields = fields
        self.references: set[FieldReference] = set()
        self.ctx = ctx

    def visit_Attribute(self, node):
        if is_field(node, self.fields):
            if type(node.ctx) in self.ctx:
                self.references.add(
                    FieldReference(
                        field=Field(name=node.attr, type=typeof_node(node).simplify()),
                        node=node,
                        ref_node=node,
                    )
                )
        self.visit(node.value)


class FieldReferenceCollector(NodeVisitor):
    """
    Collect all field references in a node.
    """

    # TODO: Fix this. Should take env as argument, check type of attr obj and
    # then check fields for that type.
    def __init__(
        self, fields: set[Field], cls: Type | None = None, *, ctx=(Load, Store, Del)
    ):
        self.fields = fields
        self.references: set[Field] = set()
        self.ctx = ctx

    def visit_Attribute(self, node: Attribute):
        if is_field(node, self.fields):
            if type(node.ctx) in self.ctx:
                self.references.add(
                    Field(name=node.attr, type=typeof_node(node).simplify())
                )
        self.visit(node.value)
