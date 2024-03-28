"""
This module provides useful types used throughout the codebase.
"""

from ast import Attribute, ClassDef, Constant, FunctionDef, List, keyword, expr
from collections import UserDict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple, NewType
from networkx import DiGraph

if TYPE_CHECKING:
    from vpy.typechecker.pyanalyze.value import Value


VersionId = NewType("VersionId", str)


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


class Graph(DiGraph):
    def __init__(self, *, graph: list[Version] = []):
        super().__init__()
        for version in graph:
            self.add_node(version, label=version.name)
        for version in graph:
            for upgrade in version.upgrades:
                try:
                    uv = next(v for v in graph if v.name == upgrade)
                    self.add_edge(version, uv, label="upgrades")
                except:
                    pass
            for replace in graph:
                try:
                    rv = next(v for v in graph if v.name == replace)
                    self.add_edge(version, rv, label="replaces")
                except:
                    pass

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


class Lens(NamedTuple):
    v_from: VersionId
    v_target: VersionId
    attr: str
    node: FunctionDef | None


class Lenses(UserDict[VersionId, dict[VersionId, dict[str, Lens]]]):
    def find_lens(
        self, *, v_from: VersionId, v_to: VersionId, attr: str
    ) -> Lens | None:
        try:
            return self.data[v_from][v_to][attr]
        except KeyError:
            return None

    def add_lens(
        self,
        v_from: VersionId,
        v_to: VersionId,
        attr: str,
        lens_node: FunctionDef | None,
    ) -> None:
        from vpy.lib.utils import get_to

        if v_from not in self.data:
            self.data[v_from] = {}
        if v_to not in self.data[v_from]:
            self.data[v_from][v_to] = {}
        if attr not in self.data[v_from][v_to]:
            target = get_to(lens_node) if lens_node is not None else v_to
            self.data[v_from][v_to][attr] = Lens(
                v_from=v_from, v_target=target, attr=attr, node=lens_node
            )
        return None


class Field(NamedTuple):

    name: str
    type: "Value"

    def __eq__(self, __value: object) -> TYPE_CHECKING:
        if isinstance(__value, Field):
            return (
                self.name == __value.name
                and self.type.simplify() == __value.type.simplify()
            )
        return False


class FieldReference(NamedTuple):
    node: expr
    field: Field
    ref_node: Attribute


class VersionedMethod(NamedTuple):
    name: str
    interface: FunctionDef
    implementation: FunctionDef


@dataclass
class ClassEnvironment:
    bases: dict[VersionId, set[VersionId]] = field(default_factory=dict)
    fields: dict[VersionId, set[Field]] = field(default_factory=dict)
    methods: dict[VersionId, set[VersionedMethod]] = field(default_factory=dict)
    get_lenses: Lenses = field(default_factory=Lenses)
    put_lenses: Lenses = field(default_factory=Lenses)
    method_lenses: Lenses = field(default_factory=Lenses)
    versions: "Graph" = field(default_factory=Graph)


@dataclass
class Environment:
    bases: dict[str, dict[VersionId, set[VersionId]]] = field(default_factory=dict)
    fields: dict[str, dict[VersionId, set[Field]]] = field(default_factory=dict)
    methods: dict[str, dict[VersionId, set[VersionedMethod]]] = field(
        default_factory=dict
    )
    get_lenses: dict[str, Lenses] = field(default_factory=dict)
    put_lenses: dict[str, Lenses] = field(default_factory=dict)
    method_lenses: dict[str, Lenses] = field(default_factory=dict)
    versions: dict[str, "Graph"] = field(default_factory=dict)
