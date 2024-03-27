from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def __init__(self):
        self.x = 1

    # Field `x` is redefined as a str in version 2, thus we need a lens from version 1 for this field.
    @at("2")
    def __init__(self):
        self.x = "1"

    @at("2")
    def m(self) -> str:
        self.x = "2"
        return self.x

    @get("1", "2", "x")
    def lens_x1(self) -> str:
        return str(self.x)

    @get("2", "1", "x")
    def lens_x2(self) -> int:
        return int(self.x)
