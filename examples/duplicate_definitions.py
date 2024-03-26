from vpy.decorators import version, at


@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self): ...
    @at("2")
    def m(self): ...

    # This definition throws an error since there already exists a definition of method `m` at version 1.
    # @at("1")
    # def m(self): ...
