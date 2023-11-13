from ast import (
    Attribute,
    Call,
    ClassDef,
    Del,
    FunctionDef,
    Load,
    Module,
    Name,
    NodeVisitor,
    Store,
    expr,
)
import inspect
from types import ModuleType
from typing import Type

from pyanalyze.ast_annotator import annotate_code
from pyanalyze.value import AnySource, AnyValue, TypedValue, Value
from vpy.lib.lib_types import FieldName, Graph, Version, VersionId
import uuid


class ClassFieldCollector(NodeVisitor):
    """
    Collects fields defined in a class at version v.
    """

    def __init__(self, cls_ast: ClassDef, cls_methods: list[str], v: VersionId):
        self.__cls_methods = cls_methods
        self.__cls_ast = cls_ast
        self.__v = v
        self.fields: set[FieldName] = set()

    def visit_ClassDef(self, node: ClassDef):
        # Ignore inner classes?
        pass

    def visit_FunctionDef(self, node: FunctionDef):
        # Only look in methods defined at version v.
        if get_at(node) != self.__v:
            return None
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, Attribute) and is_obj_attribute(
                target, obj_type=self.__cls_ast.name
            ):
                if target.attr not in self.__cls_methods:
                    self.fields.add(FieldName(target.attr))

    def visit_AnnAssign(self, node):
        if isinstance(node.target, Attribute) and is_obj_attribute(
            node.target, obj_type=self.__cls_ast.name
        ):
            if node.target.attr not in self.__cls_methods:
                self.fields.add(FieldName(node.target.attr))

    def visit_AugAssign(self, node):
        if isinstance(node.target, Attribute) and is_obj_attribute(
            node.target, obj_type=self.__cls_ast.name
        ):
            if node.target.attr not in self.__cls_methods:
                self.fields.add(FieldName(node.target.attr))


class FieldReferenceCollector(NodeVisitor):
    def __init__(self, fields: set[FieldName], cls: Type | None = None):
        self.fields = fields
        self.references: set[str] = set()

    # visit function/method call
    def visit_Attribute(self, node):
        if is_field(node, self.fields):
            # if cls is not None:
            self.references.add(node.attr)
        self.visit(node.value)


# TODO: What kind of fields? Only self?
def fields_in_function(node: FunctionDef, fields: set[FieldName]) -> set[str]:
    visitor = FieldReferenceCollector(fields)
    visitor.visit(node)
    return visitor.references


def get_self_obj(node: FunctionDef) -> str:
    return node.args.args[0].arg


def fresh_var() -> str:
    return f"_{str(uuid.uuid4().hex)}"


# TODO: fields should be dict[ClassName, set[FieldName]]
def is_field(node: Attribute, fields: set[FieldName]) -> bool:
    return is_obj_attribute(node) and node.attr in fields


def get_obj_attribute(
    obj: expr,
    attr: str,
    ctx: Load | Store | Del = Load(),
    obj_type: Value = AnyValue(AnySource.default),
    attr_type: Value = AnyValue(AnySource.default),
) -> Attribute:
    obj_attr = Attribute(value=obj, attr=attr, ctx=ctx)
    obj_attr.value.inferred_value = obj_type
    obj_attr.inferred_value = attr_type
    return obj_attr


def has_get_lens(cls_node: ClassDef, get_lens_node: FunctionDef) -> bool:
    for e in cls_node.body:
        if isinstance(e, FunctionDef) and e.name == get_lens_node.name:
            return any(
                isinstance(d, Call)
                and isinstance(d.func, Name)
                and (d.func.id == "get")
                for d in e.decorator_list
            )
    return False


def has_put_lens(cls_node: ClassDef, get_lens_node: FunctionDef) -> bool:
    for e in cls_node.body:
        if isinstance(e, FunctionDef) and e.name == get_lens_node.name:
            return any(
                isinstance(d, Call)
                and isinstance(d.func, Name)
                and (d.func.id == "put")
                for d in e.decorator_list
            )
    return False


def is_obj_attribute(node: Attribute, obj_type: str | None = None) -> bool:
    if isinstance(node.value.inferred_value, TypedValue):
        node_t = node.value.inferred_value.get_type()
        if node_t is not None:
            return True if obj_type is None else obj_type == node_t.__name__
    return False


def graph(cls_ast: ClassDef) -> Graph:
    return Graph(
        graph={
            v.name: v
            for v in [
                Version(d.keywords)
                for d in cls_ast.decorator_list
                if isinstance(d, Call)
                and isinstance(d.func, Name)
                and d.func.id == "version"
            ]
        }
    )


def parse_module(module: ModuleType) -> Module:
    src = inspect.getsource(module)
    tree = annotate_code(src)
    return tree


def parse_class(module: ModuleType, cls: Type) -> tuple[ClassDef, Graph]:
    tree = parse_module(module)
    cls_ast = [
        node
        for node in tree.body
        if isinstance(node, ClassDef) and node.name == cls.__name__
    ][0]
    g = graph(cls_ast)
    return (cls_ast, g)


def is_lens(node: FunctionDef) -> bool:
    return any(
        isinstance(d, Call)
        and isinstance(d.func, Name)
        and (d.func.id in ["get", "put"])
        for d in node.decorator_list
    )


def get_at(node: FunctionDef) -> VersionId:
    """
    Returns the version where a method is defined.
    """
    return VersionId(
        [
            d
            for d in node.decorator_list
            if isinstance(d, Call)
            and isinstance(d.func, Name)
            and d.func.id in ["get", "at", "put"]
        ][0]
        .args[0]
        .value
    )


def get_decorator(node: FunctionDef, dec_name: str | list[str]) -> Call | None:
    for dec in node.decorator_list:
        if isinstance(dec, Call):
            if isinstance(dec.func, Name) and dec.func.id == dec_name:
                return dec
    return None
