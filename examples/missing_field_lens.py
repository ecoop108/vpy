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
        return ""

    # Uncomment the following lines to fix the code.

    # @get("init", "full", "y")
    # def lens_y(self):
    #     return self.x + 1

    # @get("full", "init", "x")
    # def lens_x(self):
    #     return self.y + 1
