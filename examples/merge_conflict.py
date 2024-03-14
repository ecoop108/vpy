from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="last", upgrades=["init"])
@version(name="full", upgrades=["init"])
# @version(name="merge", replaces=["init", "full", "last"])
class C:
    """Version `init` introduces no methods. Then, branches `last` and `full` introduce separate definitions of method `m`.
    Version `merge` joins versions `full` and `last` as a replacement for version `init`.
    """

    @at("full")
    def b(self) -> str: ...

    @at("last")
    def b(self) -> str: ...

    # @at("merge")
    # def b(self) -> str:
    #     """Version `merge` must introduce a definition of `m` to solve the conflict between the two branhces, otherwise the
    #     program does not typecheck.
    #     This definition is then available to clients in versions `init`, `full`, and `last`.
    #     """
    #     ...


@version(name="init")
@version(name="last", replaces=["init"])
@version(name="full", replaces=["init"])
@version(name="merge", replaces=["init", "full", "last"])
class D:
    """In this case, versions `last` and `full` replace version `init`. Each introduces a definition of method `m`.
    This poses a conflict since definitions introduced in replacement versions should be available to previous clients.
    As such, this program does not type check. We must remove either definition, or change the version graph
    — introducing a merge definition does not resolve the conflict.
    """

    @at("full")
    def b(self) -> str: ...

    @at("last")
    def b(self) -> str: ...

    @at("merge")
    def b(self) -> str: ...
