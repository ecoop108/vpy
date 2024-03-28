from vpy.decorators import at, get, version


### Required parameter addition ###
@version(name="1")
@version(name="2", replaces=["1"])
@version(name="3", replaces=["2"])
class A:
    @at("1")
    def m(self): ...

    # In version 2 we add a required parameter, `p`, to method `m`.
    # To have this method correctly available for version 1, we define the lens for this method, `lens_m`, to state how
    # the transition is performed.
    @at("2")
    def m(self, p: int): ...

    # A call to method `m` for clients in version 1 will be dispatched to the definition of version 2 using `lens_m`.
    @get("1", "2", "m")
    def lens_m(self, f):
        return f(123)

    # In version 3 we remove a required parameter, `p`, from method `m`.
    # To have this method correctly available for version 2, we define the lens for this method, `lens_m`, to state how
    # the transition is performed.
    @at("3")
    def m(self): ...

    @get("2", "3", "m")
    def lens_m2(self, f, p: int):
        return f()


### Optional parameter removal ###
@version(name="1")
@version(name="2", replaces=["1"])
class B:
    @at("1")
    def m(self, p=None): ...

    # In version 2 we remove an optional parameter, `p`, from method `m`.
    # To have this method correctly available for version 1, we define the lens for this method, `lens_m`, to state how
    # the transition is performed.
    @at("2")
    def m(self): ...

    # A call to method `m` for clients in version 1 will be dispatched to the definition of version 2 using `lens_m`.
    @get("1", "2", "m")
    def lens_m(self, f, p=None):
        return f()


### Optional parameter addition ###
@version(name="1")
@version(name="2", replaces=["1"])
class C:
    @at("1")
    def m(self): ...

    # In version 2 we add an optional parameter, `p`, to method `m`. Since this parameter is optional, there is no need
    # to introduce any lenses as this definition is compatible with clients in version 1. For such clients, the default
    # value of the parameter is used when evaluating the method body.
    @at("2")
    def m(self, p=None): ...


### Parameter re-ordering ###
@version(name="1")
@version(name="2", replaces=["1"])
class D:
    @at("1")
    def m(self, x, y): ...

    # In version 2 we reorder parameters `x` and `y` of method `m`. To have this method correctly available for version
    # 1, we define the lens for this method, `lens_m`, to state how the transition is performed.

    @at("2")
    def m(self, y, x): ...

    # This lens reflects the reordering of parameters by calling `f` (which will map to the definition of `m` at version
    # 2) with the parameters switched from the original call.
    @get("1", "2", "m")
    def lens_m(self, f, x, y):
        return f(y, x)


### Parameter default value addition ###
@version(name="1")
@version(name="2", replaces=["1"])
class E:
    @at("1")
    def m(self, p): ...

    # In version 2 we add a default value to parameter `p`. Since this parameter is (now) optional, there is no need to
    # introduce any lenses as this definition is compatible with clients in version 1 (they must pass an
    # argument to `p`).

    @at("2")
    def m(self, p=None): ...


### Parameter default value removal ###
@version(name="1")
@version(name="2", replaces=["1"])
class F:
    @at("1")
    def m(self, p=None): ...

    # In version 2 we remove the default value to parameter `p`, thus making it required.     # To have this method
    # correctly available for version 1, we define the lens for this method, `lens_m`, to state how the transition is
    # performed.
    @at("2")
    def m(self, p): ...

    @get("1", "2", "m")
    def lens_m(self, f, p=None):
        return f(p)


### Parameter default value change ###
@version(name="1")
@version(name="2", replaces=["1"])
class G:
    @at("1")
    def m(self, p=True): ...

    # In version 2 we change the default value to parameter `p`, from `True` to `False`. Since the type of `p` is
    # unchanged, the program type checks correctly. However, the developer may want to express this semantic change in
    # the form of a lens so that clients in version 1 using the default parameter can use the new value (`True`).
    @at("2")
    def m(self, p=False): ...

    @get("1", "2", "m")
    def lens_m(self, f, p=True):
        return f(not p)
