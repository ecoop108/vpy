from copy import deepcopy
from dataclasses import InitVar, dataclass, field


@dataclass
class Version():
    kws: InitVar[str]
    name: str = field(init=False)
    replaces: list[str] = field(init=False)
    upgrades: list[str] = field(init=False)

    def __post_init__(self, kws):
        self.replaces = []
        self.upgrades = []
        for k in kws:
            if k.arg == 'name':
                self.name = k.value.value
            if k.arg == 'upgrades':
                self.upgrades = [v.value for v in k.value.elts]
            if k.arg == 'replaces':
                self.replaces = [v.value for v in k.value.elts]


class Graph(dict):

    def delete(self, v):
        copy = {str(k): deepcopy(v) for k, v in self.items()}
        del copy[v]
        for val in copy.values():
            if v in val.upgrades:
                val.upgrades.remove(v)
            if v in val.replaces:
                val.replaces.remove(v)
        return copy
