from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="full", replaces=["init"])
class C:
    @at("init")
    def a(self):
        pass

    @at("full")
    def a(self):
        x = 1
        pass

    @at("full")
    def a(self):
        pass
