# This example shows the detection of wrongly-typed method lenses.
# To run the type checker, open the terminal pane in the editor and run:

# vpy -i wrong_method_lens.py -t init

from vpy.decorators import at, get, version


# There are two versions, with the same fields (empty set).
@version(name="init")
@version(name="full", replaces=["init"])
class Name:

    @at("init")
    def m(self, x) -> bool:
        return True

    # The signature in version `full` is different from version `init`. As such, the lens for this method (`init` => `full`) is
    # required to upgrade clients without breaking.
    @at("full")
    def m(self) -> bool:
        return False

    # The lens signature is missing the `x` argument, at version init. And its return type does match the return type at
    # version `init`.
    #
    # To fix, add the `x` parameter and change the return type annotation to `bool`, as suggested in the error message.
    @get("init", "full", "m")
    def lens_m(self, f) -> int:
        return not f()
