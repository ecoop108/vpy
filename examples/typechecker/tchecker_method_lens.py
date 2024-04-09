# This example shows the detection of missing method lenses.

from vpy.decorators import at, get, version


@version(name="1")
@version(name="2", replaces=["1"])
@version(name="3", replaces=["2"])
class C:
    @at("1")
    def x(self) -> str: ...

    @at("2")
    def y(self) -> str: ...

    # This lens is not well-formed since from and to versions are the same.
    @get("1", "1", "x")
    def lens_y(self, f) -> str: ...

    # This lens is not well-formed since method `y` does not exist in version 1.
    @get("1", "2", "y")
    def lens_y(self, f) -> str: ...

    # This lens is not well-formed since method `x` does not exist in version 2.
    @get("1", "2", "x")
    def lens_x(self, f) -> str: ...

    @at("1")
    def m(self): ...

    @at("2")
    def m(self): ...

    # This lens is not well-formed since the interface of method `m` in version 3 is defined at version 2, so the lens
    # must be for that version.
    @get("1", "3", "m")
    def lens_m(self, f): ...


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    # Method `m` does not require lenses since its signature is the same in both versions, which means clients from 1
    # can use the definition of 2 without their code breaking.
    @at("1")
    def m(self) -> str: ...

    @at("2")
    def m(self) -> str: ...


@version(name="1")
@version(name="2", upgrades=["1"])
class C:
    # In this case, version 2 upgrades version 1. As such, the changes are not backported to clients in version 1 so the
    # signature of `m` can change freely.
    @at("1")
    def m(self) -> str: ...

    @at("2")
    def m(self, x) -> bool: ...


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
