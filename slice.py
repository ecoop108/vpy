import ast
from typing import Type

from adapt import tr_class


def rw(cls, v) -> Type:
    sl = tr_class(cls, v)
    s = ast.unparse(sl)
    print(s)
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]


def slice(cls, v):
    return tr_class(cls, v)
