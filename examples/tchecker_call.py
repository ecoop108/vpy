from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", upgrades=["1"])
class C:

    @at("1")
    def b(self) -> str:
        x = 1
        return ""

    @at("2")
    def b(self) -> bool:
        return True

    # This definition is not well typed since the result of method `b` in version 1 has type `str`
    @at("1")
    def m(self) -> bool:
        return self.b()

    @at("2")
    def n(self) -> bool:
        return self.b()
