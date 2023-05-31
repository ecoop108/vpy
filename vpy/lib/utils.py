import ast
import inspect
from typing import TypeVar
from vpy.lib.lib_types import Graph, Version


def graph(cls_ast: ast.ClassDef):
    return Graph({
        v.name: v
        for v in [Version(d.keywords) for d in cls_ast.decorator_list]
    })


def parse_class(cls) -> tuple[ast.ClassDef, Graph]:
    src = inspect.getsource(cls)
    cls_ast: ast.ClassDef = ast.parse(src).body[0]
    g = graph(cls_ast)
    return (cls_ast, g)


def is_lens(node):
    return any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and (
            d.func.id == 'get' or d.func.id == 'put')
        for d in node.decorator_list)


def get_at(node):
    return [d for d in node.decorator_list
            if d.func.id == 'at'][0].args[0].value


T = TypeVar('T', bound=ast.AST)


def remove_decorators(node: T) -> T:
    exclude = ['at', 'version', 'run']
    for child in ast.walk(node):
        new_decorators = []
        if isinstance(child, ast.FunctionDef) or isinstance(
                child, ast.ClassDef):
            for decorator in child.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                        decorator.func, ast.Name):
                    print(decorator.func.id, decorator.func.id in exclude)
                    if decorator.func.id in exclude:
                        continue
                    else:
                        new_decorators.append(decorator)
            child.decorator_list = new_decorators
    return node
