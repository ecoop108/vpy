# This example shows the detection of missing field lenses.

from vpy.decorators import at, get, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self):
        self.x = 1

    # Field `x` is redefined as a str in version 2, thus we need a lens from version 1 for this field.
    @at("2")
    def m(self):
        self.x = "1"
        self.x += "0"

    # @get("1", "2", "x")
    # def lens_x1(self) -> str:
    #     return str(self.x)

    # This lens is required to rewrite method `m` of version `2` because there is an assignment to field `x`.

    # @get("2", "1", "x")
    # def lens_x2(self) -> int:
    #     return int(self.x)


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def __init__(self):
        self.x = 1
        self.z = "1"

    # Field `x` is redefined as a str in version 2
    @at("2")
    def __init__(self):
        self.y = 1
        self.w = 3

    @at("2")
    def m(self):
        # This method is available for version 1 so a get lens for field `y` is required
        return self.y
        # self.w = 3
        # return self.y

    @at("2")
    def n(self):
        # This method is available for version 1, so we need to check if this assignment produces any side effects in
        # version 1.
        self.y = 3
        # To do so, we inspect all field lenses from version 2 to version 1 to find references of `y`. Then,
        # we use their corresponding put lenses to rewrite the assignment. In this case, an assignment to field `y` will
        # have side effects on fields `x` and `z` of version 1, since `y` is referenced in both these lenses. If there
        # are other field references in these lenses, then we also require a get lens for each reference. In this case,
        # the lens for field `z` also references field `w`, so we need a get lens for that field.
        # When these conditions are met, this assignment is rewritten as:
        # self.x = self.lens_x(y=3)
        # self.z = self.lens_z(y=3, self.lens_w())

    @get("2", "1", "x")
    def lens_x(self) -> int:
        return self.y

    @get("2", "1", "z")
    def lens_z(self) -> str:
        return str(self.y + self.w)

    # Uncomment this to fix the error from the return statement in method `m`
    @get("1", "2", "y")
    def lens_y(self) -> int: ...

    # Uncomment this to fix the error from the assignment in method `n`
    @get("1", "2", "w")
    def lens_w(self) -> int: ...
