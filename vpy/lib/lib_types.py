from copy import deepcopy
from dataclasses import InitVar, dataclass, field
from typing import NewType

VersionIdentifier = NewType('VersionIdentifier', str)

@dataclass
class Version():
    kws: InitVar[str]
    name: VersionIdentifier = field(init=False)
    replaces: list[VersionIdentifier] = field(init=False)
    upgrades: list[VersionIdentifier] = field(init=False)

    def __post_init__(self, kws):
        self.replaces = []
        self.upgrades = []
        for k in kws:
            if k.arg == 'name':
                self.name = VersionIdentifier(k.value.value)
            if k.arg == 'upgrades':
                self.upgrades = [VersionIdentifier(v.value) for v in k.value.elts]
            if k.arg == 'replaces':
                self.replaces = [VersionIdentifier(v.value) for v in k.value.elts]


class Graph(dict):

    def delete(self, v) -> 'Graph':
        copy = Graph({str(k): deepcopy(v) for k, v in self.items()})
        del copy[v]
        for val in copy.values():
            if v in val.upgrades:
                val.upgrades.remove(v)
            if v in val.replaces:
                val.replaces.remove(v)
        return copy

    def replacements(self, v: VersionIdentifier) -> list[Version]:
        return [w for w in self.values() if v in w.replaces]
