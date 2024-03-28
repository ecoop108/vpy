from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def __init__(self):
        self.x = 1

    # In version 2, field `x` is renamed to `y`
    @at("2")
    def __init__(self):
        self.y = 1

    @at("2")
    def m(self):
        return self.y

    # The renaming of field `x` to `y` is expressed by the lenses below.
    @get("2", "1", "x")
    def lens_x(self) -> int:
        return self.y

    @get("1", "2", "y")
    def lens_y(self) -> int:
        return self.x
