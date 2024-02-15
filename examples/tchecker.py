from vpy.decorators import at, version


@version(name="init")
@version(name="bugfix", replaces=["init"])
class Name:
    @at("init")
    def __init__(self, first: str, last: str):
        self.first = first
        self.last = last

    @at("init")
    def display(self) -> str:
        return f"{self.first}, {self.last}"

    @at("bugfix")
    def display(self) -> str:
        return len(f"{self.last}, {self.first}")
