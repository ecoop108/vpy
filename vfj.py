from ast import unparse, parse
import functools
import inspect
from slice import rw, slice
import types

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
            if scope is not None:
                vars.update(scope)
            for n, cls in dict(vars).items():
                if inspect.isclass(cls):
                    rwn = rw(cls, v)
                    vars.update(locals())
                    exec(f'global {n}\n{n}=rwn')
            return f()

        return wrapper_run

    return decorator_run

@version(name='start')
@version(name='full', replaces=['start'])
class Name:

    @at('start')
    def __init__(self, first, last):
        self.first = first
        self.last = last

    @at('full')
    def __init__(self, full):
        self.full_name = full

    @at('full')
    @lens('full', 'start', 'first')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[0]
        return self.full_name

    @at('full')
    @lens('full', 'start', 'last')
    def lens_last(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[1]
        return ''

    @at('start')
    @lens('start', 'full', 'full_name')
    def lens_full(self):
        return f"{self.first} {self.last}"

    @at('start')
    def first_name(self):
        return self.first

    @at('full')
    def get(self):
        return self.full_name


@run('full', globals())
def main():
    obj = Name('Rolling Stones')
    print(obj.get())
    print(obj.first_name())
    #b()

@run('start', globals())
def b():
    ob = Name("axs","ai")
    print(ob.first_name())


if __name__ == "__main__":
    main()

