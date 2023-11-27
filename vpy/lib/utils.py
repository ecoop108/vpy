from ast import (
    Assign,
    Attribute,
    Call,
    ClassDef,
    Constant,
    Del,
    FunctionDef,
    Load,
    Module,
    Name,
    NodeVisitor,
    Return,
    Store,
    expr,
)
import ast
import inspect
from types import ModuleType
from typing import Type

from pyanalyze.ast_annotator import annotate_code
from pyanalyze.value import AnySource, AnyValue, TypedValue, Value, KnownValue
from vpy.lib.lib_types import Field, Graph, Version, VersionId
import uuid


class ClassFieldCollector(NodeVisitor):
    """
    Collects fields defined in a class at version v.
    """

    def __init__(self, cls_ast: ClassDef, cls_methods: list[str], v: VersionId):
        self.__cls_methods = cls_methods
        self.__cls_ast = cls_ast
        self.__v = v
        self.fields: set[Field] = set()

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
                    self.fields.add(Field(name=target.attr, type=target.inferred_value))

    def visit_AnnAssign(self, node):
        if isinstance(node.target, Attribute) and is_obj_attribute(
            node.target, obj_type=self.__cls_ast.name
        ):
            if node.target.attr not in self.__cls_methods:
                field_type = AnyValue(AnySource(AnySource.default))
                if isinstance(node.annotation, Name):
                    field_type = TypedValue(node.annotation.id)
                elif isinstance(node.annotation, Constant):
                    field_type = TypedValue(node.annotation.value)
                self.fields.add(Field(node.target.attr, type=field_type))

    def visit_AugAssign(self, node):
        if isinstance(node.target, Attribute) and is_obj_attribute(
            node.target, obj_type=self.__cls_ast.name
        ):
            if node.target.attr not in self.__cls_methods:
                self.fields.add(
                    Field(name=node.target.attr, type=node.target.inferred_value)
                )


class FieldReferenceCollector(NodeVisitor):
    def __init__(self, fields: set[Field], cls: Type | None = None):
        self.fields = fields
        self.references: set[str] = set()

    # visit function/method call
    def visit_Attribute(self, node):
        if is_field(node, self.fields):
            # if cls is not None:
            self.references.add(node.attr)
        self.visit(node.value)


# TODO: What kind of fields? Only self?
def fields_in_function(node: FunctionDef, fields: set[Field]) -> set[str]:
    visitor = FieldReferenceCollector(fields)
    visitor.visit(node)
    return visitor.references


def get_self_obj(node: FunctionDef) -> str:
    return node.args.args[0].arg


def fresh_var() -> str:
    return f"_{str(uuid.uuid4().hex)}"


def is_field(node: Attribute, fields: set[Field]) -> bool:
    return is_obj_attribute(node) and any(field.name == node.attr for field in fields)


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
    if isinstance(node.value.inferred_value, KnownValue):
        node_t = node.value.inferred_value.val
        return True if obj_type is None else obj_type == node_t.__name__
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


def create_init(g: Graph, cls_ast: ClassDef, v: VersionId) -> FunctionDef:
    from vpy.lib.lookup import fields_lookup

    inherited_fields = fields_lookup(g, cls_ast, v)
    # Create function parameters
    self_param = ast.arg(arg="self", annotation=None)
    init_params = []
    for param in inherited_fields:
        arg = ast.arg(arg=param.name)
        if isinstance(param.type, KnownValue):
            arg.annotation = Name(id=param.type.get_type().__name__)
        if isinstance(param.type, TypedValue):
            arg.annotation = Name(id=str(param.type.typ))
        init_params.append(arg)

    params = [self_param] + init_params

    # Create the function arguments node
    arguments = ast.arguments(
        args=params,
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
        posonlyargs=[],
    )

    # Create the function body consisting of assigning each argument to the corresponding field
    assign_statements = []
    for param in inherited_fields:
        lhs = get_obj_attribute(
            obj=ast.Name(id="self", ctx=ast.Load()),
            attr=param.name,
            obj_type=cls_ast.inferred_value,
            # attr_type=param.type,
        )
        rhs = Name(id=param.name, ctx=Load())
        annotation = None
        if isinstance(param.type, KnownValue):
            annotation = Name(id=param.type.get_type().__name__)
        if isinstance(param.type, TypedValue):
            annotation = Name(id=param.type.get_type().__name__)
        assign = ast.AnnAssign(
            target=lhs,
            annotation=annotation,
            value=rhs,
            simple=0,
        )
        assign_statements.append(assign)

    # Create the __init__ function node
    return FunctionDef(
        name="__init__",
        args=arguments,
        body=assign_statements,
        decorator_list=[
            ast.Call(func=Name(id="at"), args=[Constant(value=v)], keywords=[])
        ],
        returns=None,
    )


def create_identity_lens(
    g: Graph, cls_ast: ClassDef, v: VersionId, t: VersionId, field: Field
) -> FunctionDef:
    # Create function parameters
    self_param = ast.arg(arg="self", annotation=None)

    # Create the function arguments node
    arguments = ast.arguments(
        args=[self_param],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
        posonlyargs=[],
    )

    # Create the function body consisting of assigning each argument to the corresponding field
    lens_return = Return(
        get_obj_attribute(
            obj=Name(id="self"), attr=field.name, obj_type=cls_ast.inferred_value
        )
    )
    # Set return type
    return_type = None
    if isinstance(field.type, KnownValue):
        return_type = Name(id=field.type.get_type().__name__)
    if isinstance(field.type, TypedValue):
        return_type = Name(id=str(field.type.typ))
    # Create the __init__ function node
    lens = FunctionDef(
        name=f"__lens_{field.name}_{v}_{t}__",
        args=arguments,
        body=[lens_return],
        decorator_list=[
            ast.Call(
                func=Name(id="get"),
                args=[Constant(value=v), Constant(value=t), Constant(value=field.name)],
                keywords=[],
            )
        ],
        returns=return_type,
    )

    lens.inferred_value = field.type
    return lens
