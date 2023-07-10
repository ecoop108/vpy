import ast
import inspect
import importlib
from vpy.lib.slice import eval_slice
from vpy.lib.transformers.decorators import RemoveDecoratorsTransformer


class ReplaceCallsTransformer(ast.NodeTransformer):

    def __init__(self, cls_name, v):
        self.cls_name = cls_name
        self.v = v

    def visit_Name(self, node):

        if node.id == self.cls_name:
            node.id = self.cls_name + '_' + self.v
        return node


def run(fun, version, *args, **kwargs):
    mod = inspect.getmodule(fun)
    if mod is None:
        raise Exception("Module does not exist")
    classes = {}
    for m in inspect.getmembers(mod, inspect.isclass):
        if m[1].__module__ == mod.__name__:
            classes[m[0]] = eval_slice(mod, getattr(mod, m[0]), version)
    # rewrite function calls
    src = inspect.getsource(fun)
    f_ast = ast.parse(src)
    for cls_name in classes:
        f_ast = ReplaceCallsTransformer(cls_name, version).visit(f_ast)
    f_ast = RemoveDecoratorsTransformer().visit(f_ast)

    # register new classes
    globs = fun.__globals__
    locs = {}
    for cls_name, cls in classes.items():
        importlib.import_module(mod.__name__)
        setattr(mod, f"{cls_name}_{version}", cls)

    # register new functions
    compiled_code = compile(f_ast, '<ast>', 'exec')
    exec(compiled_code, globs, locs)

    # run wrapped function after rewrite
    result = locs[fun.__name__](*args, **kwargs)

    # teardown runtime
    for cls_name, cls in classes.items():
        importlib.import_module(mod.__name__)
        delattr(mod, f"{cls_name}_{version}")
    return result
