# This example shows the application of field lenses to rewrite code for clients to upgrade without breaking.

from vpy.decorators import at, get, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self) -> int:
        self.x = 1
        return 0

    # The definition of `m` introduced here should be available to clients in
    # version 1. To rewrite this method we use the synthesized put lens for
    # field `x` (which is the only field affected by changes to field `y`). To
    # see the results, extract a slice of this module for version 1 and inspect
    # the code for method `m`. Notice that here we don't need a method lens
    # since the signature of both definitions (in version 1 and 2) are the same.
    @at("2")
    def m(self) -> int:
        self.y = "2"
        return 0

    @get("1", "2", "y")
    def lens_y(self) -> str:
        return str(self.x)

    # The definition of this lens is merely used to synthesize a put lens for
    # field `y`. If you comment this lens you will see a warning from the type
    # checker that the assignment to field `y` has no effects in version 1.

    # @get("2", "1", "x")
    # def lens_x(self) -> int:
    #     return int(self.y)


@version(name="1")
@version(name="2", replaces=["1"])
class A:
    @at("1")
    def __init__(self):
        self.x = self.y = 1

    @at("1")
    def m(self):
        return self.x + self.y

    # Fields defined in `__init__` are considered to be explicitly defined and
    # as such override parent fields.

    # In this case, field `x` has the same type between versions 1 and 2. As
    # such, if the developer does not define an explicit get lens, we can use
    # the identity lens between both versions.

    # Note that the same does not happen for field `y`, because it is not
    # defined in version 2. Therefore a lens is mandatory for the program to
    # type-check.
    @at("2")
    def __init__(self):
        self.x = 1

    # If you extract a slice for version 2, method `m` uses the lens for field
    # `y` and the identity lens for field `x` (i.e. it is not rewritten in any
    # way). If you uncomment the following lens for field `x` and then extract a
    # slice again you wqill notice that the program now uses the lens to rewrite
    # the field in method `m`.

    # @get("2", "1", "x")
    # def lens_x(self):
    #     return 123

    @get("2", "1", "y")
    def lens_y(self):
        return self.x
