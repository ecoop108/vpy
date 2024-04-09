from vpy.decorators import at, version


@version(name="1")
# Throws an error: version 1 is already defined
@version(name="1")
# Throws errors: since version 3 can not relate to itself; version ids must be string literals
@version(name="3", replaces=["3", "a" + "a"])
class C: ...


@version(name="1")
class D:
    # This definition will throw an error since version 2 is not defined.""
    @at("2")
    def m(self): ...

    # This definition will throw an error since it has no version annotation.""
    def n(self): ...


# This throws an error because there is a cycle in the graph
@version(name="1", upgrades=["2"])
@version(name="2", upgrades=["3"])
@version(name="3", upgrades=["1"])
class E: ...
