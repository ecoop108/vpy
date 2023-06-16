import ast
import inspect
from types import ModuleType
from typing import Type, TypeVar

from pyanalyze.ast_annotator import annotate_code
from vpy.lib.lib_types import Graph, Version, VersionId
import uuid


def get_self_obj(node: ast.FunctionDef) -> str:
    return node.args.args[0].arg


def fresh_var() -> str:
    return f"_{str(uuid.uuid4().hex)}"


def is_field(node: ast.Attribute, self_obj: str, fields: set[str]) -> bool:
    return is_obj_attribute(node, self_obj) and node.attr in fields


def obj_attribute(
    obj: str, attr: str,
    ctx: ast.Load | ast.Store | ast.Del = ast.Load()) -> ast.Attribute:
    return ast.Attribute(value=ast.Name(id=obj, ctx=ast.Load()),
                         attr=attr,
                         ctx=ctx)


def has_get_lens(cls_node: ast.ClassDef,
                 get_lens_node: ast.FunctionDef) -> bool:
    for e in cls_node.body:
        if isinstance(e, ast.FunctionDef) and e.name == get_lens_node.name:
            return any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
                    d.func.id == 'get') for d in e.decorator_list)
    return False


def has_put_lens(cls_node: ast.ClassDef,
                 get_lens_node: ast.FunctionDef) -> bool:
    for e in cls_node.body:
        if isinstance(e, ast.FunctionDef) and e.name == get_lens_node.name:
            return any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
                    d.func.id == 'put') for d in e.decorator_list)
    return False


# TODO: fix for nested attributes
def is_obj_attribute(node: ast.Attribute, obj: str) -> bool:
    if isinstance(node.value, ast.Name) and node.value.id == obj:
        return True
    return False


def graph(cls_ast: ast.ClassDef) -> Graph:
    return Graph(
        graph={
            v.name: v
            for v in [
                Version(d.keywords) for d in cls_ast.decorator_list
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                and d.func.id == 'version'
            ]
        })


def parse_module(module: ModuleType) -> ast.Module:
    src = inspect.getsource(module)
    tree = annotate_code(src)
    return tree


def parse_class(module: ModuleType, cls: Type) -> tuple[ast.ClassDef, Graph]:
    tree = parse_module(module)
    cls_ast = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == cls.__name__
    ][0]
    g = graph(cls_ast)
    return (cls_ast, g)


def is_lens(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
            d.func.id in ['get', 'put'])
        for d in node.decorator_list)


def get_at(node: ast.FunctionDef) -> VersionId:
    return [
        d for d in node.decorator_list if isinstance(d, ast.Call)
        and isinstance(d.func, ast.Name) and d.func.id in ['get', 'at', 'put']
    ][0].args[0].value  # type: ignore


def get_decorator(node: ast.FunctionDef,
                  dec_name: str | list[str]) -> ast.Call | None:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name) and dec.func.id == dec_name:
                return dec
    return None


T = TypeVar('T', bound=ast.AST)


def remove_decorators(node: T) -> T:
    remove = ['at', 'version', 'run', 'get', 'put']
    for child in ast.walk(node):
        new_decorators = []
        if isinstance(child, (ast.FunctionDef, ast.ClassDef)):
            for decorator in child.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                        decorator.func, ast.Name):
                    if decorator.func.id not in remove:
                        new_decorators.append(decorator)
            child.decorator_list = new_decorators
    return node
