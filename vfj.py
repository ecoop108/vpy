import functools
import inspect
from slice import rw
import types
import importlib
import ast
from adapt import remove_decorators

def lens(frm, to, field):

    def decorator_version(cl):

        @functools.wraps(cl)
        def wrapper_version(*args, **kwargs):
            return cl(*args, **kwargs)

        return wrapper_version

    return decorator_version


def at(name):

    def decorator_version(cl):

        @functools.wraps(cl)
        def wrapper_version(*args, **kwargs):
            return cl(*args, **kwargs)

        return wrapper_version

    return decorator_version


def version(name, replaces=[], upgrades=[]):

    def decorator_version(cl):
        return cl

    return decorator_version


class ReplaceCallsTransformer(ast.NodeTransformer):

    def __init__(self, cls_name, v):
        self.cls_name = cls_name
        self.v = v

    def visit_Name(self, node):

        if node.id == self.cls_name:
            node.id = self.cls_name+'_'+self.v
        return node

def run(v):

    def decorator_run(f):

        @functools.wraps(f)
        def wrapper_run(*args, **kwargs):
            
            # rewrite classes in function module
            mod = inspect.getmodule(f)
            classes = {}
            for m in inspect.getmembers(mod, inspect.isclass):
                if m[1].__module__ == mod.__name__:
                    classes[m[0]] = rw(mod.__name__, getattr(mod, m[0]), v)
            
            # rewrite function calls
            src=inspect.getsource(f)
            f_ast=ast.parse(src)
            for cls_name in classes:
                f_ast = ReplaceCallsTransformer(cls_name, v).visit(f_ast)
            f_ast = remove_decorators(f_ast)

            # register new classes
            globs = f.__globals__
            locs = {}
            for cls_name, cls in classes.items():
                importlib.import_module(mod.__name__)
                setattr(mod, f"{cls_name}_{v}", cls)
            # register new functions
            compiled_code = compile(f_ast, '<ast>', 'exec')
            exec(compiled_code, globs, locs)
            
            # run wrapped function after rewrite
            result = locs[f.__name__]()

            # teardown runtime
            for cls_name, cls in classes.items():
                importlib.import_module(mod.__name__)
                delattr(mod,  f"{cls_name}_{v}")
            return result
        return wrapper_run

    return decorator_run
