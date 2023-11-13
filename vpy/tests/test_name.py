from pyanalyze.ast_annotator import annotate_code
from vpy.decorators import at, get, version
from vpy.lib.lib_types import VersionId
import pytest
from vpy.lib.lookup import fields_lookup
import ast

START = VersionId("start")
FULL = VersionId("full")


@version(name=START)
@version(name=FULL, replaces=[START])
class Name:
    @at(START)
    def __init__(self, first: str, last: str):
        self.first: str = first
        self.last: str = last

    @at(FULL)
    def __init__(self, full: str):
        self.full_name: str = full

    @get(FULL, START, "first")
    def lens_first(self) -> str:
        if " " in self.full_name:
            return self.full_name.split()[0]
        return self.full_name

    @get(FULL, START, "last")
    def lens_last(self) -> str:
        if " " in self.full_name:
            return self.full_name.split()[1]
        return ""

    @get(START, "full", "full_name")
    def lens_full(self):
        return f"{self.first} {self.last}"


@pytest.fixture
def model():
    import sys

    module = sys.modules[__name__]
    from vpy.lib.utils import parse_class

    return parse_class(module, Name)


def test_fields(model):
    cls_ast, g = model
    fields_start = fields_lookup(g, cls_ast, START)
    assert fields_start == {"first", "last"}
    fields_full = fields_lookup(g, cls_ast, FULL)
    assert fields_full == {"full_name"}
    m = ast.parse(
        """
@at('full')
def m(self):
    self.x = 123"""
    ).body[0]
    cls_ast.body.append(m)
    cls_src = ast.unparse(cls_ast)
    cls_ast = annotate_code(cls_src)
    fields_full = fields_lookup(g, cls_ast, FULL)
    assert fields_full == {"full_name", "x"}


# def test_tr_select_methods(model):
#     from vpy.lib.lookup import method_lookup
#     import ast
#     cls_ast, g = model
#     mdef = method_lookup(g, cls_ast, m='reverse', v=VersionId('full'))
#     assert mdef is not None
#     assert get_at(mdef) == 'start'

#     m = ast.parse('''
# @at('full')
# def reverse(self):
#     print(1)''').body[0]
#     cls_ast.body.append(m)

#     mdef = method_lookup(g, cls_ast, m='reverse', v=VersionId('full'))
#     assert mdef is not None
#     assert get_at(mdef) == 'full'

#     mdef = method_lookup(g,
#                          cls_ast,
#                          m='new_method',
#                          v=VersionId('full'))
#     assert mdef is None

#     m = ast.parse('''
# @at('second')
# def new_method(self):
#     print(1)''').body[0]
#     cls_ast.body.append(m)

#     mdef = method_lookup(g,
#                          cls_ast,
#                          m='new_method',
#                          v=VersionId('full'))
#     assert mdef is None
#     mdef = method_lookup(g,
#                          cls_ast,
#                          m='new_method',
#                          v=VersionId('start'))
#     assert mdef is None
#     mdef = method_lookup(g,
#                          cls_ast,
#                          m='new_method',
#                          v=VersionId('second'))
#     assert mdef is not None
#     assert get_at(mdef) == 'second'


# def test_base(model):
#     from vpy.lib.lookup import base
#     import ast
#     cls_ast, g = model
#     assert base(g=g, cls_ast=cls_ast,
#                 v=VersionId('start')) == (VersionId('start'),
#                                                   {'first', 'last'})
#     assert base(g=g, cls_ast=cls_ast,
#                 v=VersionId('second')) == (VersionId('start'),
#                                                    {'last', 'first'})
#     assert base(g=g, cls_ast=cls_ast,
#                 v=VersionId('full')) == (VersionId('full'),
#                                                  {'full_name'})

#     # add method that sets a new field
#     m = ast.parse('''
# @at('second')
# def a(self):
#     self.x = 1
#     self.xyz = 123''').body[0]
#     cls_ast.body.append(m)
#     assert base(g=g, cls_ast=cls_ast,
#                 v=VersionId('second')) == (VersionId('second'),
#                                                    {'last', 'xyz', 'x'})
#     assert base(
#         g=g, cls_ast=cls_ast,
#         v=VersionId('second'))[0] == VersionId('second')
