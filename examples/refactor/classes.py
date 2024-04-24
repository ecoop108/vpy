from vpy.decorators import version, run


@version(name="1")
@version(name="2", replaces=["1"])
class A: ...


@version(name="1")
class B: ...


# Class B is not defined in version 2 of this module
@run("2")
def main():
    print(A())
    print(B())
