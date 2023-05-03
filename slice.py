import ast
from typing import Type

from adapt import tr_class


def rw(mod, cls, v) -> Type:
    sl = tr_class(mod, cls, v)
    s = ast.unparse(sl)
    # return s
    print(s)
    out = [None]
    exec(s + f'\nout[0]={cls.__name__}_{v}')
    return out[0]
