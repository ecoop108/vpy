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
        self.x = {}

    @at("2")
    def m(self) -> str:
        # a = self.x
        self.x[1] = "10"
        # self.x += "12"
        return self.x[1]

    @get("1", "2", "x")
    def lens_x1(self) -> dict:
        return {self.x: self.x}

    # # This lens is required to rewrite method `m` because there is an assignment to field `x`.

    # @get("2", "1", "x")
    # def lens_x2(self) -> int:
    #     return self.x[1]
