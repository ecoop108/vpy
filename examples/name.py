from vpy.decorators import at, get, run, version


@version(name='start')
@version(name='s', replaces=['start'])
@version(name='full', replaces=['s'])
class Name:

    @at('start')
    def __init__(self, first: str, last: str):
        self.first: str = first
        self.last: str = last

    @at('s')
    def __init__(self, first: str, last: str):
        self.f: str = first
        self.l: str = last

    @at('full')
    def __init__(self, full: str):
        self.full_name: str = full

    @get('start', 's', 'f')
    def lens_f(self) -> str:
        return self.first

    @get('start', 's', 'l')
    def lens_l(self) -> str:
        return self.last

    @get('s', 'start', 'first')
    def lens_first(self) -> str:
        return self.f

    @get('s', 'start', 'last')
    def lens_last2(self) -> str:
        return self.l

    @get('full', 's', 'f')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            first = self.full_name.split(' ')[0]
            return first
        return self.full_name

    @get('full', 's', 'l')
    def lens_last1(self) -> str:
        if ' ' in self.full_name:
            last = self.full_name.split(' ')[1]
            return last
        return ''

    @get('s', 'full', 'full_name')
    def lens_full(self):
        return f"{self.f} {self.l}"

    @at('start')
    def reverse(self):
        return self.last + ", " + self.first

    @at('full')
    def get(self):
        return self.full_name

    # @at('full')
    # def set_name(self, val: str):
    #     self.full_name = val

    # @at('start')
    # def set_last(self, some_name):
    #     self.last, self.first, y = x = ("1","2",3)
    #     self.last = some_name


@run('full')
def main():
    obj = Name('Rolling Stones')
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
