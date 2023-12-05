"""
This module provides useful types used throughout the codebase.
"""

from ast import Attribute, Constant, FunctionDef, List, keyword, expr
from collections import UserDict, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import DefaultDict, NamedTuple, NewType
import networkx as nx
from pyanalyze.value import Value, CanAssignContext

VersionId = NewType("VersionId", str)


class Lens(NamedTuple):
    v_from: VersionId
    v_target: VersionId
    field: str
    node: FunctionDef


class Lenses(UserDict[VersionId, dict[str, dict[VersionId, Lens]]]):
    def get(self, v_from: VersionId, v_to: VersionId, field_name: str) -> Lens | None:
        try:
            return self.data[v_from][field_name][v_to]
        except KeyError:
            return None

    def put(
        self, v_from: VersionId, v_to: VersionId, field_name: str, lens: FunctionDef
    ) -> None:
        if v_from not in self.data:
            self.data[v_from] = {}
        if field_name not in self.data[v_from]:
            self.data[v_from][field_name] = {}
        self.data[v_from][field_name][v_to] = Lens(
            v_from=v_from, v_target=v_to, field=field_name, node=lens
        )
        return None

    def has_lens(self, v_from: VersionId, field_name: str, v_to: VersionId) -> bool:
        try:
            return v_to in self.data[v_from][field_name]
        except KeyError:
            return False


class Field(NamedTuple):
    name: str
    type: Value


class FieldReference(NamedTuple):
    node: expr
    field: Field
    ref_node: Attribute


@dataclass
class Environment:
    fields: dict[str, dict[VersionId, set[Field]]]
    get_lenses: Lenses
    put_lenses: Lenses
    method_lenses: Lenses
    bases: dict[VersionId, VersionId]


class Version:
    def __init__(self, kws: list[keyword]):
        replaces = set()
        upgrades = set()
        for k in kws:
            if k.arg == "name" and isinstance(k.value, Constant):
                self.name = VersionId(k.value.value)
            if k.arg == "upgrades" and isinstance(k.value, List):
                upgrades = {
                    VersionId(v.value) for v in k.value.elts if isinstance(v, Constant)
                }
            if k.arg == "replaces" and isinstance(k.value, List):
                replaces = {
                    VersionId(v.value) for v in k.value.elts if isinstance(v, Constant)
                }
        self.upgrades = tuple(upgrades)
        self.replaces = tuple(replaces)

    def __repr__(self):
        return f"Version {self.name}"


class Graph(nx.DiGraph):
    def __init__(self, *, graph: dict[VersionId, Version] = {}):
        super().__init__()
        for version in graph.values():
            self.add_node(version)
        for version in graph.values():
            for upgrade in version.upgrades:
                if upgrade in graph:
                    self.add_edge(version, graph[upgrade], label="upgrades")
            for replace in version.replaces:
                if replace in graph:
                    self.add_edge(version, graph[replace], label="replaces")

    def find_version(self, v: VersionId) -> Version | None:
        for version in self.nodes:
            if version.name == v:
                return version
        return None

    def all(self) -> list[Version]:
        return list(self.nodes)

    def parents(self, v: VersionId) -> set[VersionId]:
        """Returns the ids of versions that v either upgrades or replaces."""
        if version := self.find_version(v):
            return set(version.upgrades + version.replaces)
        return set()

    def delete(self, v: VersionId) -> "Graph":
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

    def upgrades(self, v: VersionId) -> list[Version]:
        return [w for w in self.nodes if v in w.upgrades]

    def tree(self):
        tree = []

        def make_tree_node(g: Graph, root: Version):
            node = dict()
            commits = g.replacements(root.name)
            branches = g.upgrades(root.name)
            node[root.name] = {
                "commits": [make_tree_node(g, r) for r in commits],
                "branches": [make_tree_node(g, r) for r in branches],
            }
            return node

        roots = [node for node, out_degree in self.out_degree if out_degree == 0]
        for node in roots:
            tree.append(make_tree_node(self, node))
        return tree
