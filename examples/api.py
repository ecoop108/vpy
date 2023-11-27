from vpy.decorators import at, get, version, run


@version(name="v1")
@version(name="v2", replaces=["v1"])
@version(name="v4", replaces=["v1"])
@version(name="v5", replaces=["v2", "v4"])
class Library:
    @at("v1")
    def __init__(self):
        self.dogs = ["Golden Retriever", "Pug", "Pitbull"]
        self.first = "x"
        self.last = "y"

    @at("v2")
    def __init__(self):
        self.dogs_dict = {"A": ["Golden Retriever", "Pug"], "B": ["Pitbull"]}
        self.full = "x y"

    @at("v5")
    def __init__(self):
        self.full_5 = "x y"

    @get("v2", "v1", "first")
    def lens_first(self):
        return self.full.split[" "[0]]

    @get("v2", "v1", "last")
    def lens_last(self):
        return self.full.split[" "[1]]

    @get("v1", "v2", "full")
    def lens_full(self):
        return f"{self.first} {self.last}"

    @get("v2", "v5", "full_5")
    def lens_full(self):
        return f"{self.full} 5"

    @get("v5", "v2", "full")
    def lens_full(self):
        return f"{self.full_5} 222"

    @get("v2", "v1", "dogs")
    def lens_dogs(self):
        return [x for v in self.dogs_dict.values() for x in v]

    @get("v1", "v2", "dogs_dict")
    def lens_dogs_dict(self):
        return {"A": self.dogs}

    # @at("v1")
    # def has_breed(self, breed: str):
    #     return breed in self.dogs

    @at("v1")
    def get_all(self) -> list[str]:
        other = Library()
        a = x(other.dogs.pop(), x=other.dogs.pop(), y=other.dogs)
        return a

    # @at("v2")
    # def get_all(self) -> list[str]:
    #     return self.dogs_dict

    # @at("v4")
    # def get_all(self) -> list[str]:
    #     return []

    @at("v5")
    def get_all(self):
        # self.full = "2"
        self.full_5 = 2
        return 2

    # @at("v1")
    # def change_dog(self, dog, idx: "Library"):
    #     # self.dogs.append(dog)
    #     other = Library()
    #     if True:
    #         b = other.get_all()
    #         b.pop()
    #         if self.has_breed("pug"):
    #             idx.dogs.pop()
    #         else:
    #             idx.dogs.append("pug")
    #         # a = b
    #         # x = a
    #         # print(x)
    #         # p.x = [5]
    #         ### xxx = self.get_all()
    #         ### xxx.pop()
    #         ### put(xxx)
    #         # a = 2, other.dogs
    #         # a[1].pop()
    #         # if other.dogs.pop():
    #         #     return None
    #     else:
    #         b = other.dogs.pop()

    # @at("v2")
    # def add_dog(self, key, dog):
    #     if key in self.dogs_dict:
    #         self.dogs_dict[key].append(dog)
    #     else:
    #         side_effect_function(x=self.dogs_dict)
