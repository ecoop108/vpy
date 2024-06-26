# This example shows the application of method lenses to rewrite code for clients to upgrade without breaking, even in
# the presence of breaking change.

from typing import Callable
from vpy.decorators import at, get, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self, x: int) -> bool:
        x = x + 1
        return x == 1

    @at("2")
    def m(self) -> int:
        return 0

    # The following lens describes how clients in version `2` can use the (previous) definition introduced in version
    # `1`.

    # The signature of the lens matches the signature of `m` at version `1` (so that client calls don't
    # break).

    # The parameter `f` is a pointer to the function `m` at version `2`. It allows the developer to state how the
    # parameters and the return results map between the two versions.

    # This lens is used to rewrite code at version `1` that makes calls to method `m`.

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
