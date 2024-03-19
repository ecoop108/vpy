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


def version(name: str, replaces=[], upgrades=[]):

    def decorator_version(cl):
        return cl

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


def at(name):

    def overload(func):
        """
        May be used as a shortcut for ``overloaded`` and ``overloads(f)``
        when the overloaded function `f` can be automatically identified.
        """
        fn = unwrap(func)
        fname = get_full_name(fn)
        try:
            return register(__registry[fname], func, version=name)
        except KeyError:
            __registry[fname] = overloaded(func, version=name)
            return __registry[fname]

    return overload


def overloaded(func, version):
    """
    Introduces a new overloaded function and registers its first implementation.
    """
    fn = unwrap(func)

    def dispatcher(*args, **kwargs):

        resolved = None
        resolved = dispatcher.__functions[version]
        if resolved:
            return resolved(*args, **kwargs)

    dispatcher.__dict__.update(
        __functions={},
    )

    for attr in ("__module__", "__name__", "__qualname__", "__doc__"):
        setattr(dispatcher, attr, getattr(fn, attr, None))

    return register(dispatcher, func, version)


__registry = {}


def register(dispatcher, func, version):
    """
    Registers `func` as an implementation on `dispatcher`.
    """
    wrapper = None
    if isinstance(func, (classmethod, staticmethod)):
        wrapper = type(func)
        func = func.__func__
    if isinstance(dispatcher, (classmethod, staticmethod)):
        wrapper = None
    dp = unwrap(dispatcher)
    # All clear; register the function.
    dp.__functions[version] = func
    if wrapper is None:
        wrapper = lambda x: x
    if func.__name__ == dp.__name__:
        # The returned function is going to be bound to the invocation name
        # in the calling scope, so keep returning the dispatcher.
        return wrapper(dispatcher)
    else:
        return wrapper(func)


def unwrap(func):
    while hasattr(func, "__func__"):
        func = func.__func__
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def get_full_name(obj):
    return obj.__module__ + "." + obj.__qualname__
