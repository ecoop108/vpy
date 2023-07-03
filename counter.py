from vpy.decorators import at, get, version


@version(name='3', upgrades=['2'])
@version(name='2', upgrades=['1'])
@version(name='1')
class Name:

    @at('1')
    def __init__(self):
        self.y = 2
        self.a = 2

    @at('2')
    def __init__(self):
        self.z = 3
        self.xx = 1

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

    @get('3', '1', 'a')
    def lens_a(self):
        return self.w + 4

    @at('2')
    def m(self, other: 'Name'):
        other.xx = 2

    @get('2', '1', 'y')
    def lens_y(self):
        # self.xxx()
        return self.z - 1

    # @at('3')
    # def fx(a):
    #     a.m(a)
    #     a.w += 3

    @at('1')
    def f(self):
        self.y = 3
        return self.y + self.a
