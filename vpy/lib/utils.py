import ast
from typing import TypeVar

def is_lens(node):
    return any(d.func.id == 'lens' for d in node.decorator_list)


def get_at(node):
    return [d for d in node.decorator_list
            if d.func.id == 'at'][0].args[0].value

T = TypeVar('T', bound=ast.AST)
def remove_decorators(node: T) -> T:
    exclude = ['at', 'version', 'lens', 'run']
    for child in ast.walk(node):
        new_decorators = []
        if isinstance(child, ast.FunctionDef) or isinstance(
                child, ast.ClassDef):
            for decorator in child.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                        decorator.func,
                        ast.Name) and decorator.func.id in exclude:
                    pass
                else:
                    new_decorators.append(decorator)
            child.decorator_list = new_decorators
    return node
