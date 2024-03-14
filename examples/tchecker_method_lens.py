# This example shows the detection of missing method lenses.

from vpy.decorators import at, get, version


# There are two versions, with the same fields (empty set).
@version(name="1")
@version(name="2", replaces=["1"])
class C:
    # Method display does not require lenses since its signature is the same, which means clients from 1 can use the
    # def1ion of 2 without their code breaking.
    @at("1")
    def m(self) -> str:
        return ""

    @at("2")
    def m(self) -> str:
        return ""


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    # In this case, the signature of method `m` is different in versions 1 and 2 (return type and parameters don't
    # match). To allow client code in version 1 to use the definition from version 2 (as specified in the version
    # graph), the type checker require a lens for method `m` from version 1 to version 2.
    @at("1")
    def m(self, x) -> bool: ...

    @at("2")
    def m(self, *, x) -> str: ...

    # You can uncomment the lens below and then the program type checks.
    # @get("1", "2", "e")
    # def lens_e(self, f) -> bool: ...


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    # In this case, we provide a wrongly-typed lens for method `m`: the signature does not match the signature of `m` in
    # version 1. To fix the program change `z` to `x`.
    @at("1")
    def m(self, x) -> bool: ...
    @at("2")
    def m(self, y) -> str: ...

    @get("1", "2", "m")
    def lens_m(self, f, z) -> bool: ...
