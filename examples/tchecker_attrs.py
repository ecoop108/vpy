from vpy.decorators import at, get, run, version


@version(name="init")
@version(name="full", replaces=["init"])
class C:
    @at("init")
    def a(self):
        self.x = 1
        self.z = 1

    @at("init")
    def b(self):
        return self.x

    @at("full")
    def a(self):
        self.y = 2
        self.z = "1"

    @at("full")
    def b(self):
        # This should throw an error since field `x` does not exist in version `full`.
        return self.x + self.y

    @get("full", "init", "x")
    def l_x(self):
        return self.y

    @get("init", "full", "y")
    def l_y(self):
        return self.x

    @get("full", "init", "z")
    def l_zi(self) -> int:
        # This should throw an error since field `z` in version `full` is of type `str`.
        print(self.z / 2)
        return int(self.z)

    @get("init", "full", "z")
    def l_zf(self) -> str:
        return str(self.z)
