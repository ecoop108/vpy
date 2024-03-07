from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="full", replaces=["init"])
class C:
    @at("init")
    def a(self) -> int:
        return self.a()

    # @at("full")
    # def a(self) -> str:
    #     x = 1
    #     return "1"

    # @at("init")
    # def b(self):
    #     return self.a()
