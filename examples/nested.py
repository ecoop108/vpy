from vpy.decorators import at, get, version


@version(name="start")
@version(name="full", replaces=["start"])
class O:
    @at("start")
    def __init__(self, f: str):
        self.f: str = f

    @at("full")
    def __init__(self, full: str):
        self.a: str = full


@version(name="start")
@version(name="full", replaces=["start"])
class Name:
    @at("start")
    def __init__(self, first: str, last: str):
        self.first: str = "123"
        self.last: str = last
        self.mirror: "Name" = Name(first, last)
        self.o: O = O(f=self.first)

    @at("full")
    def __init__(self, full: str):
        self.full_name: str = full

    @get("full", "start", "first")
    def lens_first(self) -> str:
        if " " in self.full_name:
            first = self.full_name.split(" ")[0]
            return first
        return self.full_name

    @get("full", "start", "last")
    def lens_last(self) -> str:
        if " " in self.full_name:
            last = self.full_name.split(" ")[1]
            return last
        return ""

    @get("full", "start", "mirror")
    def lens_mirror(self) -> "Name":
        return Name(full=self.full_name)

    @get("full", "start", "o")
    def lens_o(self) -> O:
        return O(full=self.full_name)

    @get("start", "full", "full_name")
    def lens_full(self):
        return f"{self.first} {self.last}"

    @at("start")
    def set_mirror(self, other: "Name"):
        # print(self.mirror.first)
        self.mirror.first = "aaaa"
        self.o.f = "aaaa"
        a = Name
        b = a(first="a", last=self.last)
        print(b.first)  # '123'
        # b = a(full=lens_full(first='a', last=self.lens_last()))
        # b.lens_first() => 'a'

        self.mirror = other
