from vpy.decorators import version, run


@version(name="1")
@version(name="2", replaces=["1"])
@version(name="3", replaces=["2"])
class A: ...


@version(name="1")
@version(name="2", replaces=["1"])
class B: ...


@run("2")
def main():
    print(B())


if __name__ == "__main__":
    main()
