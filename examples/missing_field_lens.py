# This example shows the detection of missing field lenses.
# To run the type checker, open the terminal pane in the editor and run:

# vpy -i missing_field_lens.py -t init

from vpy.decorators import at, get, version


# There are two versions, with the different fields (version `init` has field `x` and version `full` has field `y`).
# Version `full` replaces `init`, so method `m` must be available there. Since method `m` uses a field (`x`) to which
# there is no lens, the type checker throws an error.


# The same happens for method `t`: since `full` is a replacement version, then `t` must be available at version `init`,
# so a lens for field `y` is required.
@version(name="init")
@version(name="full", replaces=["init"])
class Name:
    @at("init")
    def m(self) -> str:
        self.x = 1
        return ""

    @at("full")
    def t(self) -> str:
        self.y = 2
        self.m() / 2
        return ""

    # Uncomment the following lines to fix the code.

    @get("init", "full", "y")
    def lens_y(self):
        return self.x + 1

    @get("full", "init", "x")
    def lens_x(self):
        return self.y + 1


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
