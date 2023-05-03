from vfj import version, at, run, lens
@version(name='start')
@version(name='full', replaces=['start'])
class Name:

    @at('start')
    def __init__(self, first, last):
        self.first = first
        self.last = last

    @at('full')
    def __init__(self, full):
        self.full_name = full

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


@run('full', globals())
def main():
    obj = Name('Rolling Stones')
    print(obj.get())
    print(obj.reverse())

@run('start', globals())
def b():
    obj = Name("abc", "def")
    print(obj.get())

if __name__ == "__main__":
    main()



# from vfj import version, at, run
# from slice import slice
# from ast import unparse


# # @version(name='start')
# # @version(name='bugfix', replaces=['start'])
# # @version(name='dec', upgrades=['start'])
# # class A:

# #     @at('start')
# #     def __init__(self, counter):
# #         self.counter = counter

# #     @at('start')
# #     def inc(self):
# #         self.counter += 2

# #     @at('bugfix')
# #     def inc(self):
# #         self.counter += 1

# #     @at('dec')
# #     def dec(self):
# #         self.counter -= 1

# # @run('dec')
# # def main():
# #     ctr = A(4)
# #     ctr.inc()
# #     ctr.dec()
# #     print(ctr.counter)
