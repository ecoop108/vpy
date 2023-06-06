from vpy.decorators import version, at, run, get, put


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
            return self.full_name.split()[0]
        return self.full_name

    @get('full', 'start', 'last')
    def lens_last(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[1]
        return ''

    @get('start', 'full', 'full_name')
    def lens_full(self):
        self.reverse()
        return f"{self.first} {self.last}"

    @at('start')
    def reverse(self):
        return self.last + ", " + self.first

    @at('full')
    def get(self):
        return self.full_name

    @at('full')
    def set_name(self, val):
        self.full_name = val

    @at('start')
    def set_last(self, some_name):
        x = self.last = self.first + "!" + some_name
        print(self.last)
        a: str = self.first
        self.last += "%%%"
        # self.full_name = self.lens_full(last=self.lens_first() + '%%%', first=
        # self.lens_first())


@run('full')
def name_main():
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


@run('dec')
def a_main():
    ctr = A(4)
    ctr.inc()
    ctr.dec()
    print(ctr.counter)


if __name__ == "__main__":
    name_main()
    # a_main()
