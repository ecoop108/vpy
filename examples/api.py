from vpy.decorators import at, get, version


@version(name="v1")
@version(name="v2", replaces=["v1"])
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

    @at("v2")
    def add_dog(self, key, dog):
        if key in self.dogs_dict:
            # how to rewrite this expr?
            self.dogs_dict[key].append(dog)
        else:
            # xxx = self.dogs_dict
            # xxx[key] = [dog]
            # self.dogs_dict = xxx
            # self.lens_dogs__(xxx)
            self.dogs_dict[key] = [dog]
