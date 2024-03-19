from vpy.decorators import at, version


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    # In this example we introduce a duplicate definition of `m` at version 2.
    @at("1")
    def m(self): ...

    @at("2")
    def m(self): ...

    @at("2")
    def m(self): ...


@version(name="1")
@version(name="2", upgrades=["1"])
class C:
    # In this example we make a reference to an non-defined attribute at version 2 (`x`)
    @at("1")
    def m(self):
        self.x = ...

    @at("2")
    def m(self):
        self.z = ...
        self.x
