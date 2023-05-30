from vpy.decorators import version, at, lens

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

    @lens('full', 'start', 'first')
    def lens_first(self) -> str:
        if ' ' in self.full_name:
            return self.full_name.split()[0]
        return self.full_name

    # @lens('full', 'start', 'last')
    # def lens_last(self) -> str:
    #     if ' ' in self.full_name:
    #         return self.full_name.split()[1]
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