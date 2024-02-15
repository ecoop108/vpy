# This example shows the detection of missing method lenses.
# To run the type checker, open the terminal pane in the editor and run:

# vpy -i missing_method_lens.py -t init

from vpy.decorators import at, get, version


# There are two versions, with the same fields (empty set).
@version(name="init")
@version(name="full", replaces=["init"])
class Name:
    # Method display does not require lenses since its signature is the same, which means clients from init can use the
    # definition of full without their code breaking.
    @at("init")
    def display(self) -> str:
        return ""

    @at("full")
    def display(self) -> str:
        return ""

    # However for method m the signature changes. The return type and the parameters are different.
    # So in this case, we require a lens from version init to version full. This allows client code, written for version
    # init, to work with the (new, replacement) definition introduced in version full, without any refactoring on the
    # client part.
    @at("init")
    def m(self, x) -> bool:
        return True

    @at("full")
    def m(self) -> int:
        return 0

    # You can uncomment the lens below and then the program type checks.
    # @get("init", "full", "m")
    # def lens_m(self, f, x) -> bool:
    #     return f() == 0
