from vpy.decorators import at, version


@version(name='1', replaces=['2'], upgrades=['3'])
@version(name='2')
@version(name='3')
class Name:

    @at('3')
    def __init__(self):
        pass

    @at('2')
    def __init__(self):
        pass
