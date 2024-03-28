# This example shows the application of field lenses to rewrite code for clients to upgrade without breaking.

from vpy.decorators import at, get, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self) -> int:
        self.x = 1
        return 0

    @at("2")
    def m(self) -> int:
        self.y = "2"
        return 0

    @get("1", "2", "y")
    def lens_y(self) -> str:
        return str(self.x)

    @get("2", "1", "x")
    def lens_x(self) -> int:
        return int(self.y)


@version(name="1")
@version(name="2", replaces=["1"])
class A:
    @at("1")
    def __init__(self):
        self.x = self.y = 1

    @at("1")
    def m(self):
        return self.x + self.y

    # Fields defined in `__init__` are considered to be explicitly defined and as such override parent fields. In this
    # case, since field `x` has the same type between both versions 1 and 2, we can use the identity lens between both
    # versions. As such, the developer does not need to introduce any lenses for field `x`, only for field `y`.
    @at("2")
    def __init__(self):
        self.x = 1

    @get("2", "1", "x")
    def lens_x(self):
        return 1

    @get("2", "1", "y")
    def lens_y(self): ...
