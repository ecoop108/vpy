from pyanalyze.extensions import reveal_type
from vpy.decorators import at, version, get, run


@version(name='3', upgrades=['2'])
@version(name='2', upgrades=['1'])
@version(name='1')
class Name:

    @at('1')
    def __init__(self):
        self.y = 2

    @at('2')
    def __init__(self):
        self.z = 3

    @at('3')
    def __init__(self):
        self.w = 4

    @get('3', '2', 'z')
    def lens_z2(self):
        return self.w - 2

    @get('2', '3', 'w')
    def lens_w(self):
        return self.z + 2

    @get('1', '2', 'z')
    def lens_z(self):
        return self.y + 1

    @get('2', '1', 'y')
    def lens_y(self):
        return self.z - 1

    @at('1')
    def f(a):
       a.y += 3
       return a.y
