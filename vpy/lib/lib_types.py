from ast import Constant, FunctionDef, Tuple, keyword
from copy import deepcopy
from typing import NewType
import networkx as nx

VersionId = NewType('VersionId', str)

Lenses = NewType('Lenses', dict[VersionId, dict[VersionId, dict[str,
                                                                FunctionDef]]])


class Version():

    def __init__(self, kws: list[keyword]):
        replaces = set()
        upgrades = set()
        for k in kws:
            if k.arg == 'name' and isinstance(k.value, Constant):
                self.name = VersionId(k.value.value)
            if k.arg == 'upgrades' and isinstance(k.value, Tuple):
                upgrades = {
                    VersionId(v.value)
                    for v in k.value.elts if isinstance(v, Constant)
                }
            if k.arg == 'replaces' and isinstance(k.value, Tuple):
                replaces = {
                    VersionId(v.value)
                    for v in k.value.elts if isinstance(v, Constant)
                }
        self.upgrades = tuple(upgrades)
        self.replaces = tuple(replaces)

    def __repr__(self):
        return f'Version {self.name}'


class Graph(nx.DiGraph):

    def __init__(self, *, graph: dict[VersionId, Version] = {}):
        super().__init__()
        for version in graph.values():
            self.add_node(version)
        for version in graph.values():
            for upgrade in version.upgrades:
                if upgrade in graph:
                    self.add_edge(version, graph[upgrade], label='upgrades')
            for replace in version.replaces:
                if replace in graph:
                    self.add_edge(version, graph[replace], label='replaces')

    def find_version(self, v: VersionId) -> Version | None:
        for version in self.nodes:
            if version.name == v:
                return version
        return None

    def all(self) -> list[Version]:
        return list(self.nodes)

    def parents(self, v: VersionId) -> set[VersionId]:
        if version := self.find_version(v):
            return set(version.upgrades + version.replaces)
        return set()

    def delete(self, v: VersionId) -> 'Graph':
        other = deepcopy(self)
        version = other.find_version(v)
        if version is None:
            return other
        other.remove_node(version)
        for val in other.nodes:
            val.upgrades = tuple(u for u in val.upgrades if u != v)
            val.replaces = tuple(r for r in val.replaces if r != v)
        return other

    def children(self, v: VersionId) -> list[Version]:
        return [w for w in self.nodes if v in w.upgrades or v in w.replaces]

    def replacements(self, v: VersionId) -> list[Version]:
        return [w for w in self.nodes if v in w.replaces]
