import functools
import inspect
from slice import rw
import types
import importlib

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


def run(v, scope=None):

    def decorator_run(f):

        @functools.wraps(f)
        def wrapper_run(*args, **kwargs):
            vars = dict(globals())
            stmts = []
            out = []
            mod = inspect.getmodule(f)
            if scope is not None:
                vars.update(scope)
            classes = [m[0] for m in inspect.getmembers(mod, inspect.isclass) if m[1].__module__ == mod.__name__]
            for cls_name in classes:
                cls = getattr(mod, cls_name)
                rwn = rw(cls, v)
                vars.update(locals())
                importlib.import_module(mod.__name__)
                setattr(mod, cls_name, rwn)
            return f()

        return wrapper_run

    return decorator_run
