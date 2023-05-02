from ast import unparse
import functools
import inspect
from slice import rw


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


@version(name='start')
@version(name='bugfix', replaces=['start'])
@version(name='dec', upgrades=['start'])
class A:

    @at('start')
    def __init__(self, counter):
        self.counter = counter

    @at('start')
    def inc(self):
        self.counter += 2

    @at('bugfix')
    def inc(self):
        self.counter += 1

    @at('dec')
    def dec(self):
        self.counter -= 1


class AC:

    def _start___init__(self, counter):
        self.counter = counter

    def _dec___init__(self, counter):
        self._start___init__(counter)

    def _start_inc(self):
        self.counter += 2

    def _bugfix_inc(self):
        self.counter += 1

    def _dec_inc(self):
        self._bugfix_inc()

    def _dec_dec(self):
        self.counter -= 1


def run(v):

    def decorator_run(cl):

        @functools.wraps(cl)
        def wrapper_run(*args, **kwargs):
            for n, cl in globals().items():
                if inspect.isclass(cl):
                    print(n)
                    exec(f'global {n}\n{n}=rw({n}, "{v}")')
            return cl()

        return wrapper_run

    return decorator_run


@run('dec')
def main():
    ctr = A(4)
    ctr.inc()
    ctr.dec()
    print(ctr.counter)


if __name__ == "__main__":
    main()
