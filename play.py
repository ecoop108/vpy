from vpy.decorators import version, at, run, lens

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
