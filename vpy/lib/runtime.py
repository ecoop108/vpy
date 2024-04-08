import ast
import inspect
import importlib
from typing import Any, Callable, Type, TypeVar
from vpy.lib.slice import eval_slice
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer

T = TypeVar("T")


def run(
    fun: Callable[..., T], v: str, *args: tuple[Any, ...], **kwargs: dict[str, Any]
) -> T:
    # grab the module where fun is defined
    mod = inspect.getmodule(fun)
    if mod is None:
        raise Exception("Module does not exist")
    # slice all classes in module for version v
    classes: dict[str, Type[Any]] = {}
    for m in inspect.getmembers(mod, inspect.isclass):
        if m[1].__module__ == mod.__name__:
            classes[m[0]] = eval_slice(mod, getattr(mod, m[0]), v)
    # rewrite function calls
    src = inspect.getsource(fun)
    f_ast = ast.parse(src)
    f_ast = RemoveDecoratorsTransformer().visit(f_ast)

    # register new classes
    globs = fun.__globals__
    locs: dict[str, Callable[..., T]] = {}
    for cls_name, cls in classes.items():
        importlib.import_module(mod.__name__)
        setattr(mod, f"{cls_name}_{v}", cls)

    # register new functions
    compiled_code = compile(f_ast, "<ast>", "exec")
    exec(compiled_code, globs, locs)

    # run wrapped function after rewrite
    result: T = locs[fun.__name__](*args, **kwargs)

    # teardown runtime
    for cls_name, cls in classes.items():
        importlib.import_module(mod.__name__)
        delattr(mod, f"{cls_name}_{v}")
    return result
