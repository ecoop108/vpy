from vpy.decorators import at, version, get


# @version(name="1")
# @version(name="2", replaces=["1"])
# @version(name="3", replaces=["1"])
# # @version(name="3", replaces=["2"])
# @version(name="4", replaces=["2", "3"])
# class E:
#     # The following definitions create a conflict. Clients @at(1) should be able
#     # to write self.m(x=...) or self.m(y=...), depending on which was introduced
#     # first in the graph. In this case, it was version 2. As such, to solve this
#     # conflict, the developer must change the graph and have version 3 replacing
#     # version 2. Then, they can introduce the new definition and provide a method lens
#     # between both versions (the type checker will alert to this).

#     @at("2")
#     def m(self, x) -> str: ...

#     @at("3")
#     def m(self, y) -> str: ...

#     @at("4")
#     def m(self): ...


@version(name="1")
@version(name="2", replaces=["1"])
@version(name="3", replaces=["1"])
@version(name="4", replaces=["2", "3"])
class A:
    # Versions 2 and 3 introduce separate definitions of method `m`. This
    # creates a conflict in version 1 since both definitions are at the same
    # level in the version graph.
    @at("2")
    def m(self) -> str: ...

    @at("3")
    def m(self) -> str: ...

    # TODO: This should only be solvable if interface of `m` in versions 2 and 3
    # is the same, since it is introduced in a replacement version. Otherwise, the conflict can not be solved.

    # As such we
    # must introduce a new version, 4, that merges versions 2 and 3, and
    # introduces a merge definition of method `m`

    @at("4")
    def m(self) -> str: ...


@version(name="1")
@version(name="2")
@version(name="3", upgrades=["1", "2"])
@version(name="4", replaces=["3"])
class B:
    # Im this example, version 3 creates a new branch by merging versions 1 and
    # 2. Since both have definitions of method `m`, this creates a conflict.
    @at("1")
    def m(self): ...

    @at("2")
    def m(self): ...

    # To solve the conflict we either introduce a definition of `m` in version
    # 3, or add a new replacement version (4) with such a definition.
    @at("3")
    def m(self): ...

    # @at("4")
    # def m(self): ...


@version(name="1")
@version(name="2", upgrades=["1"])
@version(name="3", upgrades=["1"])
class C:
    # Versions 2 and 3 introduce separate definitions of method `m`. Since these
    # are branch versions, this does not create a conflict for clients in
    # version 1."""

    @at("3")
    def m(self) -> str: ...

    @at("2")
    def m(self) -> str: ...
