# This example shows the application of method lenses to rewrite code for clients to upgrade without breaking, even in
# the presence of breaking change.

from typing import Callable
from vpy.decorators import at, get, run, version


@version(name="1")
@version(name="2", replaces=["1"])
class Name:
    @at("1")
    def m(self, x: int) -> bool:
        x = x + 1
        return x == 1

    @at("2")
    def m(self) -> int:
        return 0

    # The following lens describes how clients in version `1` can use the (new) definition introduced in version
    # `2`.

    # The signature of the lens matches the signature of `m` at version `1` (so that client calls don't
    # break).

    # The parameter `f` is a pointer to the function `m` at version `2`. It allows the developer to state how the
    # parameters and the return results map between the two versions.

    # Method lenses allow common breaking changes such as paramater renaming or reordering, parameter introduction or
    # removal, or return type changes, to become non-breaking.

    # Using the editor extension, if you extract a slice for version `1` you can inspect how the lens is used to rewrite method `m`.
    @get("1", "2", "m")
    def lens_m_init(self, f: Callable[[], int], x: int) -> bool:
        return f() == 1

    # Client at 1 using method m.

    # Note how the implementation of method `t` also requires a lens from 1 => 2 for method m:

    # This code should be reusable at version `2`, and in that version the definition of `m` is not the one at
    # `1`.

    # As such, the developer must provide a lens for method `m` between `1` (the current context) and `2` (the
    # context of the definition of `m` at version `2`)
    @at("1")
    def t(self) -> int:
        if not self.m(12):
            return 4
        return 3

    # Client at `2` using method `m`.
    @at("2")
    def w(self) -> bool:
        return self.m() == 0

    # If the developer wants to adapt the semantics of method `m` from version `2` to clients in version `1`, they
    # can write a lens in that direction.

    # Note that this is not required. If the lens is not present, the implementation of version `2` of `m` is used
    # instead.

    # To see this in action, extract a slice of this program for version `1` and inspect method `w`.

    # Then, uncomment the following lens and extract the slice again. Now the definition of `w` uses the lens to adapt
    # the method.

    # @get("2", "1", "m")
    # def lens_m_full(self, f: Callable[[int], bool]) -> int:
    #     return not f(1)
