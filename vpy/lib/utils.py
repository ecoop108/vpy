import ast
import inspect
from typing import TypeVar
from vpy.lib.lib_types import Graph, Version, VersionIdentifier


def has_put_lens(cls_node: ast.ClassDef,
                 get_lens_node: ast.FunctionDef) -> bool:
    for e in cls_node.body:
        if isinstance(e, ast.FunctionDef) and e.name == get_lens_node.name:
            return any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
                    d.func.id == 'put') for d in e.decorator_list)
    return False


# TODO: fix for nested attributes
def is_self_attribute(node: ast.Attribute) -> bool:
    if isinstance(node.value, ast.Name) and node.value.id == 'self':
        return True
    return False


def graph(cls_ast: ast.ClassDef) -> Graph:
    return Graph({
        v.name: v
        for v in [
            Version(d.keywords) for d in cls_ast.decorator_list
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
            and d.func.id == 'version'
        ]
    })


def parse_class(cls) -> tuple[ast.ClassDef, Graph]:
    src = inspect.getsource(cls)
    cls_ast: ast.ClassDef = ast.parse(src).body[0]
    g = graph(cls_ast)
    return (cls_ast, g)


def is_lens(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
            d.func.id == 'get' or d.func.id == 'put')
        for d in node.decorator_list)


def get_at(node: ast.FunctionDef) -> VersionIdentifier:
    return [
        d for d in node.decorator_list if isinstance(d, ast.Call)
        and isinstance(d.func, ast.Name) and d.func.id in ['get', 'at']
    ][0].args[0].value


T = TypeVar('T', bound=ast.AST)


def remove_decorators(node: T) -> T:
    remove = ['at', 'version', 'run', 'get', 'put']
    for child in ast.walk(node):
        new_decorators = []
        if isinstance(child, ast.FunctionDef) or isinstance(
                child, ast.ClassDef):
            for decorator in child.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                        decorator.func, ast.Name):
                    if decorator.func.id in remove:
                        continue
                    else:
                        new_decorators.append(decorator)
            child.decorator_list = new_decorators
    return node
