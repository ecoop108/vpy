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
