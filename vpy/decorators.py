import functools
from typing import Any, Callable, LiteralString, Type
from vpy.lib.lib_types import VersionId
import vpy.lib.runtime as r


def get[T, **P](frm: str, to: str, field: str):
    def decorator_version(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        def wrapper_version(*args: P.args, **kwargs: P.kwargs) -> T:
            return fn(*args, **kwargs)

        return wrapper_version

    return decorator_version


def put[T, **P](frm: str, to: str, field: str):
    def decorator_put(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        def wrapper_version(*args: P.args, **kwargs: P.kwargs) -> T:
            return fn(*args, **kwargs)

        return wrapper_version

    return decorator_put


def version[T](
    name: str, *, replaces: list[str] = [], upgrades: list[str] = []
) -> Callable[[Type[T]], Type[T]]:
    def decorator_version(cl: Type[T]) -> Type[T]:
        return cl

    return decorator_version


def run[T, **P](v: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator_run(f: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(f)
        def wrapper_run(*args: P.args, **kwargs: P.kwargs) -> T:
            return r.run(f, VersionId(v), *args, **kwargs)

        return wrapper_run

    return decorator_run


def at[T, **P](name: LiteralString) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def overload(func: Callable[P, T]) -> Callable[P, T]:
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
            return __registry[fname]  # type:ignore

    return overload


def overloaded[T, **P](func: Callable[P, T], version: str) -> Callable[P, T]:
    """
    Introduces a new overloaded function and registers its first implementation.
    """
    fn = unwrap(func)

    def dispatcher(*args: P.args, **kwargs: P.kwargs) -> T | None:
        resolved = None
        resolved = dispatcher.__functions[version]  # type: ignore
        if resolved:
            return resolved(*args, **kwargs)

    dispatcher.__dict__.update(
        __functions={},
    )

    for attr in ("__module__", "__name__", "__qualname__", "__doc__"):
        setattr(dispatcher, attr, getattr(fn, attr, None))

    return register(dispatcher, func, version)


__registry: dict[str, Callable[..., Any]] = dict()


def register[T, **P](
    dispatcher: Callable[P, T | None], func: Callable[P, T], version: str
) -> Callable[P, T]:
    """
    Registers `func` as an implementation on `dispatcher`.
    """
    wrapper = None
    if isinstance(func, (classmethod, staticmethod)):
        wrapper = type(func)  # type: ignore
        func = func.__func__  # type: ignore
    if isinstance(dispatcher, (classmethod, staticmethod)):
        wrapper = None
    dp = unwrap(dispatcher)  # type:ignore
    # All clear; register the function.
    dp.__functions[version] = func  # type:ignore
    if wrapper is None:
        wrapper = lambda x: x  # type:ignore
    if func.__name__ == dp.__name__:
        # The returned function is going to be bound to the invocation name
        # in the calling scope, so keep returning the dispatcher.
        return wrapper(dispatcher)  # type:ignore
    else:
        return wrapper(func)  # type:ignore


def unwrap[T, **P](func: Callable[P, T]) -> Callable[P, T]:
    while hasattr(func, "__func__"):
        func = func.__func__  # type:ignore
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type:ignore
    return func


def get_full_name[T, **P](obj: Callable[P, T]) -> str:
    return obj.__module__ + "." + obj.__qualname__
