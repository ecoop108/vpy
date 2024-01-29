# This file provides more examples, particularly showcasing the rewriting of AST
# nodes that are outside the scope of the paper (e.g if and other block
# statements, multiple assignment targets, subscripts, etc.).

from typing import Callable
from vpy.decorators import at, get, version


@version(name="v1")
@version(name="v2", replaces=["v1"])
@version(name="v4", replaces=["v1"])
@version(name="v5", replaces=["v2", "v1"])
class Dogs:
    @at("v1")
    def __init__(self, n):
        self.dogs = ["1", "2", "3"]

    @at("v2")
    def __init__(self, fn: str, ln: str):
        self.dogs_dict = {"A": ["Golden Retriever", "Pug"], "B": ["Pitbull"]}

    # Lens for __init__ method from version v1 to version v2
    # Maps how to rewrite a call to __init__ in version v1 to version v2
    @get("v1", "v2", "__init__")
    def lens_v1_v2_init(self, f, *args, **kwargs):
        return f(fn="1", ln="2")

    # Lens from version v2 to dogs field of version v1
    # Maps how to get field dogs from state of version v2
    @get("v2", "v1", "dogs")
    def lens_dogs(self):
        return [x for v in self.dogs_dict.values() for x in v]

    # Lens from version v1 to dogs_dict field of version v2
    # Maps how to get field dogs_dict from state of version v1
    @get("v1", "v2", "dogs_dict")
    def lens_dogs_dict(self):
        return {"A": self.dogs}

    @at("v1")
    def has_breed(self, breed: str) -> bool:
        return breed in self.dogs

    @at("v2")
    def has_breed(self, breed_name: str) -> str:
        return "y" if breed_name in self.dogs_dict else "n"

    # Lens for has_breed method from version v2 to version v1
    # Maps how to rewrite a call to has_breed in version v1 (which returns a bool) to version v2 (which returns str)
    @get("v2", "v1", "has_breed")
    def lens_v2_v1_has_breed(self, f: Callable[[str], str], breed_name: str) -> str:
        res = f(breed_name)
        if res:
            return "y"
        return "n"

    # Lens for has_breed method from version v1 to version v2
    # Maps how to rewrite a call to has_breed in version v2 (which returns a str) to version v1 (which returns bool)
    @get("v1", "v2", "has_breed")
    def lens_v1_v2_has_breed(self, f: Callable[[str], str], breed: str) -> bool:
        res = f(breed)
        if res == "y" and self.dogs:
            return True
        return False

    @at("v1")
    def change_dog(self, dog: str, idx: int):
        self.dogs[idx] = dog
