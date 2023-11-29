from vpy.decorators import at, get, version


@version(name="v1")
@version(name="v2", replaces=["v1"])
@version(name="v4", replaces=["v1"])
@version(name="v5", replaces=["v2", "v4"])
class Library:
    @at("v1")
    def __init__(self, fn: str, ln: str):
        self.dogs = ["Golden Retriever", "Pug", "Pitbull"]
        self.first = fn + "!"
        self.last = ln + "?"

    @at("v2")
    def __init__(self, fn: str, ln: str):
        self.dogs_dict = {"A": ["Golden Retriever", "Pug"], "B": ["Pitbull"]}
        self.full = "x y"

    # @get("v1", "v2", "__init__")
    # def lens_init_1_2(self, f, *args, **kwargs):
    #     obj = self.__init__(*args, **kwargs)
    #     fn = kwargs["fn"]
    #     obj.first = fn + "!"
    #     obj.last = fn + "!"
    #     return obj

    @get("v2", "v1", "first")
    def lens_first(self):
        return self.full.split(" ")[0]

    @get("v2", "v1", "last")
    def lens_last(self):
        return self.full.split(" ")[1]

    @get("v1", "v2", "full")
    def lens_full_1_2(self):
        return f"{self.first} {self.last}"

    @get("v2", "v1", "dogs")
    def lens_dogs(self):
        return [x for v in self.dogs_dict.values() for x in v]

    @get("v1", "v2", "dogs_dict")
    def lens_dogs_dict(self):
        return {"A": self.dogs}

    @at("v1")
    def has_breed(self, breed: str) -> bool:
        return breed in self.dogs

    @at("v1")
    def get_all(self) -> list[str]:
        return self.dogs

    @at("v5")
    def has_breed(self, breed_name: str) -> str:
        return "y" if breed in self.dogs_dict else "n"

    @at("v1")
    def change_dog(self, dog, idx: "Library"):
        self.dogs.append(dog)
        self.dogs.append(dog)
        other = Library(fn="Bob", ln="Alice")
        other.first
        if True:
            b = other.get_all()
            b.pop()
            if self.has_breed(breed="pug"):
                idx.dogs.pop()
            else:
                idx.dogs.append("pug")
            a = b
            x = a
            print(x)
            a = 2, other.dogs
            a[1].pop()
            if other.dogs.pop():
                return None

    @at("v2")
    def add_dog(self, key, dog):
        if key in self.dogs_dict:
            self.dogs_dict[key].append(dog)
        else:
            side_effect_function(x=self.dogs_dict)
