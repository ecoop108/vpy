from vpy.decorators import version, at, run, lens
import pytest


@version(name='start')
@version(name='full', replaces=['start'])
@version(name='second', upgrades=['start'])
class Name:

    @at('start')
    def __init__(self, first: str, last: str):
        self.first: str = first
        self.last: str = last

    @at('full')
    def __init__(self, full: str):
        self.full_name: str = full

    @lens('full', 'start', 'first')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[0]
        return self.full_name

    @lens('full', 'start', 'last')
    def lens_last(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[1]
        return ''

    @lens('start', 'full', 'full_name')
    def lens_full(self):
        return f"{self.first} {self.last}"

    @at('start')
    def reverse(self):
        return self.last + ", " + self.first

    @at('full')
    def get(self):
        return self.full_name

    @at('start')
    def set_last(self, last):
        print(self.last)
        self.last = last


@run('full')
def name_main():
    print(1)
    obj = Name('Rolling Stones')
    print(obj.get())
    print(obj.reverse())
    obj.set_last("Stoned")
    print(obj.get())
    name_switch_context()


@run('start')
def name_switch_context():
    obj = Name("Bob", "Dylan")
    print(obj.get())


@pytest.fixture
def model():
    from vpy.lib.utils import parse_class
    return parse_class(Name)


def test_base(model):
    from vpy.lib.lookup import base
    import ast
    cls_ast, g = model
    assert base(g=g, cls_ast=cls_ast, v='start') == 'start'
    assert base(g=g, cls_ast=cls_ast, v='second') == 'start'
    assert base(g=g, cls_ast=cls_ast, v='full') == 'full'
    # add method that sets a field
    m = ast.parse('''
@at('second')
def a(self):
    self.x = 1''')
    cls_ast.body.append(m)
    assert base(g=g, cls_ast=cls_ast, v='second') == 'start'
