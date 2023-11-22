from vpy.decorators import at, get, version


@version(name="v1")
@version(name="v2", replaces=["v1"])
@version(name="v4", replaces=["v1"])
@version(name="v5", upgrades=[], replaces=["v1"])
class Library:
    @at("v1")
    def __init__(self):
        self.dogs = ["Golden Retriever", "Pug", "Pitbull"]

    @at("v2")
    def __init__(self):
        self.dogs_dict = {"A": ["Golden Retriever", "Pug"], "B": ["Pitbull"]}

    @get("v2", "v1", "dogs")
    def lens_dogs(self):
        return [x for v in self.dogs_dict.values() for x in v]

    @get("v1", "v2", "dogs_dict")
    def lens_dogs_dict(self):
        return {"A": self.dogs}

    @at("v1")
    def has_breed(self, breed: str):
        return breed in self.dogs

    @at("v1")
    def get_all(self):
        return self.dogs

    @at("v1")
    def change_dog(self, idx, dog):
        other = Library()
        if True:
            # x = 2
            a = other.dogs
            a.pop()
            # a = 2
            print(a)
            if other.dogs.pop():
                return None
        else:
            b = other.dogs.pop()

    @at("v2")
    def add_dog(self, key, dog):
        if key in self.dogs_dict:
            self.dogs_dict[key].append(dog)
        else:
            side_effect_function(x=self.dogs_dict)
