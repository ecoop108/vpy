# This file covers the running example shown in the paper (Section 2).

from typing import Callable
from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="bugfix", replaces=["init"])
@version(name="full", upgrades=["init"])
class Name:
    @at("init")
    def __init__(self, first: str, last: str):
        self.first = first
        self.last = last

    @at("full")
    def __init__(self, full: str):
        self.fullname = full

    @at("init")
    def display(self) -> str:
        return f"{self.first}, {self.last}"

    @at("bugfix")
    def display(self) -> str:
        return f"{self.last}, {self.first}"

    @at("init")
    def set_last(self, name: str):
        self.last = name

    @at("full")
    def get_full_name(self):
        return self.fullname

    @at("init")
    def m(self) -> bool:
        return True

    @at("full")
    def m(self) -> int:
        return 0

    @at("init")
    def t(self) -> bool:
        return not self.m()

    @at("full")
    def w(self) -> bool:
        return self.m() == 0

    ######### Lenses #########
    @get("full", "init", "first")
    def lens_first(self):
        if " " in self.fullname:
            return self.fullname.split(" ")[0]
        return self.fullname

    @get("full", "init", "last")
    def lens_last(self):
        if " " in self.fullname:
            return self.fullname.split(" ")[1]
        return ""

    @get("init", "full", "fullname")
    def lens_full(self):
        return f"{self.first} {self.last}"

    @get("init", "full", "m")
    def lens_m(self, f: Callable[[], int]) -> bool:
        return f() == 0


@run("full")
def main():
    obj = Name("Rolling Stones")
    print(obj.get_full_name())
    obj.set_last("Stoned")
    print(obj.get_full_name())


if __name__ == "__main__":
    main()
