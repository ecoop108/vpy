# This example shows the type-checking of class attributes in the presence of
# multiple versioned definitions.

from vpy.decorators import at, version


@version(name="1")
@version(name="2", replaces=["1"])
class A:
    @at("1")
    def m(self): ...

    @at("2")
    def m(self): ...

    # This is a duplicate definition of `m` at version 2.
    @at("2")
    def m(self): ...


@version(name="1")
@version(name="2", upgrades=["1"])
class B:
    # In this example we make a reference to non-defined attributes: attribute
    # `z` in version 1 and attribute `x` in version 2.
    @at("1")
    def m(self):
        self.x = ...
        self.z

    @at("2")
    def m(self):
        self.z = ...
        self.x
