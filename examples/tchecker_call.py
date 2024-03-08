from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="last", replaces=["init"])
@version(name="full", replaces=["init"])
@version(name="merge", replaces=["init", "full", "last"])
class C:
    # @at("init")
    # def a(self) -> bool:
    #     return True

    # @at("full")
    # def a(self) -> str:
    #     return "1"

    @at("full")
    def b(self) -> str:
        """This method is introduced in version full and available to all clients in version init."""
        return "1 2".split()

    @at("last")
    def b(self) -> str:
        """This replacement definition for `b` requires a lens from full -> last."""
        return "1"

    # @at("merge")
    # def b(self) -> str:
    #     return "1"

    @at("init")
    def m(self):
        return self.b()
