from typing_extensions import reveal_type
from vpy.decorators import at, get, run, version


@version(name='start')
@version(name='full', replaces=['start'])
class Name:

    @at('start')
    def __init__(self, first: str, last: str):
        self.first: str = first
        self.last: str = last

    @at('full')
    def __init__(self, full: str):
        self.full_name: str = full

    @get('full', 'start', 'first')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            first, _ = self.full_name.split(' ')
            return first
        return self.full_name

    @get('full', 'start', 'last')
    def lens_last(self) -> str:
        if ' ' in self.full_name:
            _, last = self.full_name.split(' ')
            return last
        return ''

    @get('full', 'start', 'x')
    def lens_x(self):
        return 4

    @get('start', 'full', 'full_name')
    def lens_full(self):
        # return self.reverse()
        return f"{self.first} {self.last}"

    @at('start')
    def reverse(self):
        self.x: int = self.x + 3
        return self.x
        # return self.last + ", " + self.first

    @at('full')
    def get(self):
        return self.full_name

    @at('full')
    def set_name(self, val: str):
        self.full_name = val

    @at('start')
    def set_last(self, some_name):
        y = self.last = self.first + "!" + some_name
        self.last = "%%%"


@run('full')
def main():
    obj = Name('Rolling Stones')
    reveal_type(obj.lens_full)
    print(obj.get())
    print(obj.reverse())
    obj.set_last("Stoned")
    print(obj.get())
    name_switch_context()


@run('start')
def name_switch_context():
    obj = Name("Bob", "Dylan")
    print(obj.get())  # Bob Dylan
    obj.set_last("Marley")


if __name__ == "__main__":
    main()
