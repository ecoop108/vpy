# This file covers (most of) the examples shown in the paper.

from typing import Callable
from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def __init__(self):
        self.x = 10

    @at("2")
    def __init__(self):
        self.y = ""

    @at("1")
    def set_x(self, x: int) -> int:
        self.x = x
        return self.x

    @at("2")
    def set_y(self, y: str):
        self.y = y
        return self.y

    @get("2", "1", "x")
    def lens_x(self):
        return int(self.y)

    @get("1", "2", "y")
    def lens_y(self):
        return str(self.x)
