from ast import AST, Constant, FunctionDef, List, Module
from logging import CRITICAL
import logging
from types import ModuleType
from typing import Any, Dict, Mapping

from networkx import NetworkXNoCycle, find_cycle
from vpy.typechecker.pyanalyze.checker import Checker
from vpy.typechecker.pyanalyze.find_unused import UnusedObjectFinder
from vpy.typechecker.pyanalyze.name_check_visitor import (
    CallSiteCollector,
    ClassAttributeChecker,
)
from vpy.typechecker.pyanalyze.node_visitor import Failure, Replacement
from vpy.typechecker.pyanalyze.value import Value
from .name_check_visitor import NameCheckVisitor
from .error_code import ErrorCode


class VersionCheckVisitor(NameCheckVisitor):
    def visit_Module(self, node) -> Value:
        self.generic_visit(node)
        if self.seen_errors:
            return
        from vpy.lib.utils import get_module_environment

        self.env = get_module_environment(self.tree)

        return super().generic_visit(node)

    def visit_ClassDef(self, node) -> Value:

        from vpy.lib.utils import get_decorators
        from vpy.lib.lib_types import Version

        version_dec = get_decorators(node, "version")
        versions = [(Version(d.keywords), d) for d in version_dec]
        for idx, (version, v_node) in enumerate(versions):
            name = next(kw for kw in v_node.keywords if kw.arg == "name")
            if not isinstance(name.value, Constant) or not isinstance(
                name.value.value, str
            ):
                self._show_error_if_collecting(
                    name.value,
                    msg=f"Version name must be a literal string: {name.value}",
                    # TODO: Create new error code for this
                    error_code=ErrorCode.duplicate_version,
                )
                return
            elif name.value.value in [w.name for (w, _) in versions[:idx]]:
                self._show_error_if_collecting(
                    name.value,
                    msg=f"Duplicate version name: {name.value.value}",
                    error_code=ErrorCode.duplicate_version,
                )
                return
            else:
                upgrades = [kw for kw in v_node.keywords if kw.arg == "upgrades"]
                replaces = [kw for kw in v_node.keywords if kw.arg == "replaces"]
                for rel_kw in upgrades + replaces:
                    if not isinstance(rel_kw.value, List):
                        # TODO: Add error code for this
                        self._show_error_if_collecting(
                            rel_kw,
                            msg=f"Related versions must be declared as a list: {rel_kw.value}",
                            error_code=ErrorCode.undefined_version,
                        )
                        return
                    else:
                        for w in rel_kw.value.elts:
                            if not isinstance(w, Constant) or not isinstance(
                                w.value, str
                            ):
                                self._show_error_if_collecting(
                                    w,
                                    msg=f"Version names must be string literals",
                                    error_code=ErrorCode.undefined_version,
                                )
                                return

                            else:
                                if w.value not in [v.name for (v, _) in versions]:
                                    self._show_error_if_collecting(
                                        w,
                                        msg=f"Undefined version: {w.value}",
                                        error_code=ErrorCode.undefined_version,
                                    )
                                    return
                                elif w.value == version.name:
                                    self._show_error_if_collecting(
                                        w,
                                        msg=f"Version {version.name} can not be related to itself.",
                                        error_code=ErrorCode.self_relation_version,
                                    )
                                    return

        try:
            from vpy.lib.utils import graph

            g = graph(node)
            cycle = find_cycle(g)
            self._show_error_if_collecting(
                node,
                f"Cycle detected in version graph: {cycle}",
                ErrorCode.cyclic_version_graph,
            )
            return
        except NetworkXNoCycle:
            pass
        self.graph = versions
        for fn in (n for n in node.body if isinstance(n, FunctionDef)):
            self.visit(fn)

        return super().visit_ClassDef(node)

    def visit_FunctionDef(self, node) -> Value:
        from vpy.lib.utils import get_at, get_decorators

        version_dec = (
            get_decorators(node, "at")
            + get_decorators(node, "get")
            + get_decorators(node, "put")
        )
        # TODO: Create error code for this
        if len(version_dec) == 0:
            self._show_error_if_collecting(node, "Missing version annotation")
            return
        if len(version_dec) > 1:
            self._show_error_if_collecting(node, "Multiple version annotations")
            return
        version_dec = version_dec[0]
        version = get_at(node)

        try:
            v = next(v for (v, _) in self.graph if v.name == version)
            return super().visit_FunctionDef(node)
        except StopIteration:
            self._show_error_if_collecting(
                version_dec,
                f"Undefined version: {version}",
                ErrorCode.undefined_version,
            )

    def _show_error_if_collecting(
        self,
        node: AST,
        msg: str | None = None,
        error_code: ErrorCode | None = None,
        *,
        replacement: Replacement | None = None,
        detail: str | None = None,
        extra_metadata: Dict[str, Any] | None = None,
    ) -> None:
        if self._is_collecting():
            return super().show_error(
                node,
                msg,
                error_code,
                replacement=replacement,
                detail=detail,
            )


class LensCheckVisitor(VersionCheckVisitor):
    def __init__(
        self,
        filename: str,
        contents: str,
        tree: Module,
        *,
        settings: Mapping[ErrorCode, bool] | None = None,
        fail_after_first: bool = False,
        verbosity: int = logging.CRITICAL,
        unused_finder: UnusedObjectFinder | None = None,
        module: ModuleType | None = None,
        attribute_checker: ClassAttributeChecker | None = None,
        collector: CallSiteCollector | None = None,
        annotate: bool = True,
        add_ignores: bool = False,
        checker: Checker,
        is_code_only: bool = False,
    ) -> None:
        super().__init__(
            filename,
            contents,
            tree,
            settings=settings,
            fail_after_first=fail_after_first,
            verbosity=verbosity,
            unused_finder=unused_finder,
            module=module,
            attribute_checker=attribute_checker,
            collector=collector,
            annotate=annotate,
            add_ignores=add_ignores,
            checker=checker,
            is_code_only=is_code_only,
        )

    def check(self, ignore_missing_module: bool = False) -> list[Failure]:
        super().visit(self.tree)
        if self.seen_errors:
            return self.all_failures
        super(VersionCheckVisitor, self).check(ignore_missing_module)
        if self.seen_errors:
            return self.all_failures
        self.visit(self.tree)
        self.tree = None
        self._lines.__cached_per_instance_cache__.clear()
        self._argspec_to_retval.clear()
        return self.all_failures

    def visit_ClassDef(self, node) -> Value:
        super().visit_ClassDef(node)
        if self.seen_errors:
            return
        from vpy.lib.utils import graph, get_class_environment, get_at

        cls_env = get_class_environment(node)
        g = graph(node)
        for v in g.all():
            methods = cls_env.methods[v.name]
            lenses_methods = {
                l.node
                for w in cls_env.get_lenses.get(v.name, {}).values()
                for l in w.values()
                if l.node is not None
            }
            for m in methods.union(lenses_methods):
                if isinstance(m, tuple):
                    assert False
                mver = get_at(m)
                if mver != v.name and mver not in cls_env.bases[v.name]:
                    for field in cls_env.fields[mver]:
                        if (
                            field.name not in cls_env.get_lenses[mver]
                            or v.name not in cls_env.get_lenses[mver][field.name]
                        ):
                            self._show_error_if_collecting(
                                m,
                                f"No path for field {field.name} between versions {mver} and {v.name}",
                            )
                            return
