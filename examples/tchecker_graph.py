from vpy.decorators import at, version


@version(name="1")

# Throws an error: version 1 is already defined
@version(name="1")

# Throws an error: since version 2 is not defined
@version(name="3", replaces=["2"])
class C:

    @at("1")
    def m(self):
        return 123 / "1"

    @at("2")
    def m(self):
        """This definition will produce an error while type checking the program since version 2 is not defined."""
        ...
