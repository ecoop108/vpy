from ast import (
    Attribute,
    Call,
    ClassDef,
    Constant,
    Del,
    FunctionDef,
    Load,
    Module,
    Name,
    Store,
)
import ast
from copy import deepcopy
import inspect
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, Type, runtime_checkable

from vpy.typechecker.pyanalyze.value import (
    AnySource,
    AnyValue,
    TypedValue,
    Value,
    KnownValue,
)

if TYPE_CHECKING:
    from vpy.typechecker.pyanalyze.name_check_visitor import NameCheckVisitor
from vpy.lib import lookup
from vpy.lib.lib_types import Environment, Field, Graph, Lenses, Version, VersionId
import uuid


def fields_in_function(node: FunctionDef, fields: set[Field]) -> set[Field]:
    from vpy.lib.visitors.fields import FieldReferenceCollector

    visitor = FieldReferenceCollector(fields)
    visitor.visit(node)
    return visitor.references


def fresh_var() -> str:
    """
    Returns a fresh unused variable name.
    """
    return f"_{str(uuid.uuid4().hex)}"


def is_field(node: Attribute, fields: set[Field] | None) -> bool:
    if fields is None:
        return False
    return is_obj_attribute(node) and any(field.name == node.attr for field in fields)


def typeof_node(node: ast.AST) -> Value | None:
    @runtime_checkable
    class Typed(Protocol):
        inferred_value: Value

    if isinstance(node, Typed):
        return node.inferred_value
    return None


def set_typeof_node(node: ast.AST, type_value: Value) -> None:
    setattr(node, "inferred_value", type_value)


def create_obj_attr(
    obj: Attribute,
    attr: str,
    ctx: Load | Store | Del = Load(),
    obj_type: Value = AnyValue(AnySource.default),
    attr_type: Value = AnyValue(AnySource.default),
) -> Attribute:
    """
    Creates an `Attribute` of the form `obj.attr` where `obj` has type
    `obj_type` and `attr` has type `attr_type`.
    """
    obj_attr = Attribute(value=obj, attr=attr, ctx=ctx)
    set_typeof_node(obj_attr.value, obj_type)
    set_typeof_node(obj_attr, attr_type)
    return obj_attr


def has_get_lens(cls_node: ClassDef, get_lens_node: FunctionDef) -> bool:
    """
    Check if the get-lens defined in `get_lens_node` is in the body of
    `cls_node`.
    """
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
    """
    Check if the put-lens defined in `put_lens_node` is in the body of
    `cls_node`.
    """
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
    node_value_t = typeof_node(node.value)
    if isinstance(node_value_t, KnownValue):
        node_t = node_value_t.val
        return True if obj_type is None else obj_type == node_t.__name__
    if isinstance(node_value_t, TypedValue):
        node_t = node_value_t.get_type()
        if node_t is not None:
            return True if obj_type is None else obj_type == node_t.__name__
    return False


def graph(cls: ClassDef) -> Graph:
    """
    Build a version graph for class `cls`.
    """
    return Graph(
        graph={
            v.name: v
            for v in [
                Version(d.keywords)
                for d in cls.decorator_list
                if isinstance(d, Call)
                and isinstance(d.func, Name)
                and d.func.id == "version"
            ]
        }
    )


def get_module_environment(mod_ast: Module):
    env = Environment()
    for node in mod_ast.body:
        if isinstance(node, ClassDef):
            g = graph(node)
            env.get_lenses[node.name] = lookup.field_lenses_lookup(g, node)
            env.put_lenses[node.name] = Lenses()
            env.method_lenses[node.name] = lookup.method_lenses_lookup(g, node)
            env.cls_ast[node.name] = deepcopy(node)
            for k in g.all():
                if node.name not in env.methods:
                    env.methods[node.name] = {}
                if node.name not in env.bases:
                    env.bases[node.name] = {}
                if node.name not in env.fields:
                    env.fields[node.name] = {}
                env.methods[node.name][k.name] = {  # type: ignore
                    m  # type: ignore
                    for m in lookup.methods_lookup(g, node, k.name)
                    if isinstance(m, FunctionDef) or m[0].name not in dir(object)
                }
                env.bases[node.name][k.name] = lookup.base_versions(g, node, k.name)
                env.fields[node.name][k.name] = lookup.fields_lookup(g, node, k.name)
    return env


def parse_module(module: ModuleType) -> tuple[Module, "NameCheckVisitor"]:
    from vpy.typechecker.pyanalyze.ast_annotator import annotate_code

    src = inspect.getsource(module)
    tree, visitor = annotate_code(src)
    return tree, visitor


def parse_class(module: ModuleType, cls: Type) -> tuple[ClassDef, Graph]:
    tree, _ = parse_module(module)
    cls_ast = [
        node
        for node in tree.body
        if isinstance(node, ClassDef) and node.name == cls.__name__
    ][0]
    g = graph(cls_ast)
    return (cls_ast, g)


def is_lens(node: FunctionDef) -> bool:
    """
    Check if the given `node` is a lens.
    """
    return any(
        isinstance(d, Call)
        and isinstance(d.func, Name)
        and (d.func.id in ["get", "put"])
        for d in node.decorator_list
    )


def get_at(node: FunctionDef) -> VersionId:
    """
    Returns the version id where method `node` is defined.
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


def get_decorator(node: FunctionDef, dec_name: str) -> Call | None:
    for dec in node.decorator_list:
        if isinstance(dec, Call):
            if isinstance(dec.func, Name) and dec.func.id == dec_name:
                return dec
    return None


def field_to_arg(field: Field) -> ast.arg:
    field_arg = ast.arg(arg=field.name)
    arg_t = annotation_from_type_value(field.type)
    field_arg.annotation = Name(id=arg_t, ctx=Load())
    set_typeof_node(field_arg.annotation, field.type)
    return field_arg


def annotation_from_type_value(val: Value) -> str:
    val = val.simplify()
    if isinstance(val, TypedValue):
        if isinstance(val.typ, str):
            return val.typ
        elif (t := val.get_type()) is not None:
            return t.__name__
        assert False
    if isinstance(val, KnownValue):
        if (t := val.get_type()) is not None:
            return t.__name__
        assert False
    return "Any"


def create_init(g: Graph, cls_ast: ClassDef, v: VersionId) -> FunctionDef:
    from vpy.lib.lookup import fields_lookup

    inherited_fields = fields_lookup(g, cls_ast, v)
    # Create function parameters
    self_param = ast.arg(arg="self", annotation=None)
    init_params = [field_to_arg(field) for field in inherited_fields]

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
        lhs = create_obj_attr(
            obj=ast.Name(id="self", ctx=ast.Load()),
            attr=param.name,
            obj_type=typeof_node(cls_ast),
            # attr_type=param.type,
        )
        rhs = Name(id=param.name, ctx=Load())
        annotation = None
        annotation = Name(id=annotation_from_type_value(param.type), ctx=Load())
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
