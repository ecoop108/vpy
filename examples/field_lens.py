# This example shows the application of field lenses to rewrite code for clients to upgrade without breaking, even in
# the presence of breaking change.

from typing import Callable
from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self) -> int:
        # self.x = 1
        return self.m()
        # return self.x

    # This case should be detected by the type system. Since this definition is used in version 1, and field y is
    # referenced in it, a lens for field y is necessary.
    @at("2")
    def b(self, z: str) -> str:
        self.y += z
        return self.y

    @get("1", "2", "y")
    def lens_y(self) -> str:
        return str()

    @get("1", "2", "m")
    def lens_m(self, f) -> int:
        return int(f(z=""))
