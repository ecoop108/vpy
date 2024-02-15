import functools
from vpy.lib.lib_types import VersionId
import vpy.lib.runtime as r


from inspect import getfullargspec


class Function(object):
    """Function is a wrap over standard python function."""

    def __init__(self, fn, version: VersionId):
        self.fn = fn
        self.version = version

    def __call__(self, *args, **kwargs):
        fn = Namespace.get_instance().get(self.fn, self.version, *args)
        if not fn:
            raise Exception("no matching function found.")
        return fn(*args, **kwargs)

    def key(self, args=None):
        """Returns the key that will uniquely identify
        a function (even when it is overloaded).
        """
        # if args not specified, extract the arguments from the
        # function definition
        if args is None:
            args = getfullargspec(self.fn).args

        return tuple([
            self.fn.__module__,
            self.fn.__class__,
            self.version,
            self.fn.__name__,
            len(args or []),
        ])


class Namespace(object):
    """Namespace is the singleton class that is responsible
    for holding all the functions.
    """

    __instance = None

    def __init__(self):
        if self.__instance is None:
            self.function_map = dict()
            Namespace.__instance = self
        else:
            raise Exception("cannot instantiate a virtual Namespace again")

    @staticmethod
    def get_instance():
        if Namespace.__instance is None:
            Namespace()
        return Namespace.__instance

    def register(self, fn, version: VersionId):
        """registers the function in the virtual namespace and returns
        an instance of callable Function that wraps the
        function fn.
        """
        func = Function(fn, version)
        self.function_map[func.key()] = fn
        return func

    def get(self, fn, version: VersionId, *args):
        """get returns the matching function from the virtual namespace.

        return None if it did not fund any matching function.
        """
        func = Function(fn, version)
        return self.function_map.get(func.key(args=args))


def at(name):

    def decorator_version(cl):
        return Namespace.get_instance().register(cl, name)
        # return cl(*args, **kwargs)

    return decorator_version


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
