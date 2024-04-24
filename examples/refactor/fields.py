from vpy.decorators import get, version, at


### Field removal ###
@version(name="1")
@version(name="2", replaces=["1"])
class A:
    @at("1")
    def __init__(self):
        self.x = self.y = 1

    @at("1")
    def m(self):
        return self.x + self.y

    @at("2")
    def __init__(self):
        # Field `x` is redefined here. However, since its type is the same, it
        # uses the identity lens to and from version 1.
        self.x = 1

        # Note that if the declared type does not match, then the identity lens
        # can not be used. Comment the previous line and uncomment the next one to see the error.

        # self.x: int | None = 1

        # This throws an error since field `y` is not defined in this version.
        # The field is (implicitly) removed because it is never assigned to in version 2.

        # print(self.y)

    @get("2", "1", "y")
    def lens_y(self): ...


### Field addition ###
@version(name="1")
@version(name="2", replaces=["1"])
class B:
    @at("1")
    def __init__(self):
        self.x = ...

    @at("2")
    def m(self):
        return self.x + self.y

    @at("2")
    def __init__(self):
        # Field `x` is redefined and field `y` is introduced. As before, since
        # the type of `x` is the same, it uses the identity lens to and from
        # version 1. For field `y`, a lens is required.
        self.x = self.y = ...

    @get("1", "2", "y")
    def lens_y(self): ...


### Field rename ###
@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def __init__(self):
        self.x = 1

    # In version 2, field `x` is renamed to `y`
    @at("2")
    def __init__(self):
        self.y = 1

    @at("2")
    def m(self):
        self.y = 3
        return self.y

    # The renaming of field `x` to `y` is expressed by the lenses below.
    @get("2", "1", "x")
    def lens_x(self) -> int:
        return self.y

    @get("1", "2", "y")
    def lens_y(self) -> int:
        return self.x
