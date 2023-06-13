import functools
import vpy.lib.runtime as r


def get(frm, to, field):

    def decorator_version(cl):

        @functools.wraps(cl)
        def wrapper_version(*args, **kwargs):
            return cl(*args, **kwargs)

        return wrapper_version

    return decorator_version


def put(frm, to, field):

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


def version(name: str, replaces=[], upgrades=[]):

    def decorator_version(cl):
        return cl

    return decorator_version


def run(v):

    def decorator_run(f):

        @functools.wraps(f)
        def wrapper_run(*args, **kwargs):
            return r.run(f, v, *args, **kwargs)

        return wrapper_run

    return decorator_run
