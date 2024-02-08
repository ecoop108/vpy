from vpy.typechecker.pyanalyze.ast_annotator import annotate_code
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
