
from vpy.decorators import at, get, run, version
import random

@version(name='start')
@version(name='full', replaces=['start'])
class Name:

    @at('start')
    def __init__(self, first: str, last: str):
        self.first: str = '123'
        self.last: str = last
        self.mirror: 'Name' = Name(first, last)

    @at('full')
    def __init__(self, full: str):
        self.full_name: str = full

    @get('full', 'start', 'first')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            first = self.full_name.split(' ')[0]
            return first
        return self.full_name

    @get('full', 'start', 'last')
    def lens_last(self) -> str:
        if ' ' in self.full_name:
            last = self.full_name.split(' ')[1]
            return last
        return ''

    @get('full', 'start', 'mirror')
    def lens_mirror(self) -> 'Name':
        return Name(full=self.full_name)

    @get('start', 'full', 'full_name')
    def lens_full(self):
        return f"{self.first} {self.last}"


    # @at('start')
    # def set_mirror_last(self, some_name):
    #     print(random.choice([1,2,3]))
    #     self.mirror.last = some_name
    #     print(self.mirror.last)

    @at('start')
    def set_mirror(self, other):
        print(self.mirror)
        a = Name
        b = a(first='a', last=self.last)
        print(b.first) # '123'
        # b = a(full=lens_full(first='a', last=self.lens_last()))
        # b.lens_first() => 'a'

        self.mirror = other



# @run('full')
# def main():
#     obj = Name('Rolling Stones')
#     print(obj.get())
#     print(obj.reverse())
#     obj.set_last("Stoned")
#     print(obj.get())
#     name_switch_context()


# @run('start')
# def name_switch_context():
#     obj = Name("Bob", "Dylan")
#     print(obj.get())  # Bob Dylan
#     obj.set_last("Marley")


# if __name__ == "__main__":
#     main()
