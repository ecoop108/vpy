# This example shows the application of field lenses to rewrite code for clients to upgrade without breaking, even in
# the presence of breaking change.

from typing import Callable
from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self) -> int:
        self.x = 1
        self.m()
        return self.x

    @at("2")
    def m(self, z: str) -> str:
        self.y += z
        self.m(z)
        return self.y

    @get("1", "2", "y")
    def lens_y(self) -> str:
        return str(self.x)

    @get("1", "2", "m")
    def lens_m(self, f) -> int:
        return int(f(z=self.x))
