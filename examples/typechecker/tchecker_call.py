# This example shows the type-checking of function calls in the presence of
# multiple versioned definitions of the same method.

from vpy.decorators import at, version


@version(name="1")
@version(name="2", upgrades=["1"])
class C:
    @at("1")
    def b(self) -> str: ...

    @at("2")
    def b(self) -> bool: ...

    # This definition is not well typed since the result of method `b` in version 1 has type `str`
    @at("1")
    def m(self) -> bool:
        return self.b()

    @at("2")
    def n(self) -> bool:
        return self.b()
