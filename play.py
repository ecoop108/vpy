from vpy.decorators import at, get, run, version


@version(name="start")
@version(name="full", replaces=["start"])
class Name:
    @at("start")
    def __init__(self, first: str, last: str):
        self.first: str = first
        self.last: str = last

    @at("full")
    def __init__(self, full: str):
        self.full_name: str = full

    @get("full", "start", "first")
    def lens_first(self) -> str:
        if " " in self.full_name:
            first, _ = self.full_name.split(" ")
            return first
        return self.full_name

    @get("full", "start", "last")
    def lens_last(self) -> str:
        if " " in self.full_name:
            _, last = self.full_name.split(" ")
            return last
        return ""

    @get("start", "full", "full_name")
    def lens_full(self):
        return f"{self.first} {self.last}"

    @at("start")
    def reverse(self):
        return self.last + ", " + self.first

    @at("full")
    def get(self):
        return self.full_name

    @at("full")
    def set_name(self, val: str):
        self.full_name = val

    @at("start")
    def set_last(self, some_name):
        self.last, self.first, y = x = ("1", "2", 3)
        self.last = some_name


@run("full")
def main():
    obj = Name("Rolling Stones")
    print(obj.get())
    print(obj.reverse())
    obj.set_last("Stoned")
    print(obj.get())
    name_switch_context()


@run("start")
def name_switch_context():
    obj = Name("Bob", "Dylan")
    print(obj.get())  # Bob Dylan
    obj.set_last("Marley")


if __name__ == "__main__":
    main()
