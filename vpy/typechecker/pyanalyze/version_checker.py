from ast import AST, ClassDef, Call, Constant, FunctionDef, List, Name
from typing import Any, Dict

from networkx import NetworkXNoCycle, find_cycle
from vpy.typechecker.pyanalyze.checker import Checker
from vpy.typechecker.pyanalyze.find_unused import UnusedObjectFinder
from vpy.typechecker.pyanalyze.node_visitor import Failure, Replacement
from vpy.typechecker.pyanalyze.value import Value
from .name_check_visitor import ClassAttributeChecker, NameCheckVisitor
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
        errors = False
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
                errors = True
                return
            elif name.value.value in [w.name for (w, _) in versions[:idx]]:
                self._show_error_if_collecting(
                    name.value,
                    msg=f"Duplicate version name: {name.value.value}",
                    error_code=ErrorCode.duplicate_version,
                )
                errors = True
            else:
                upgrades = [kw for kw in v_node.keywords if kw.arg == "upgrades"]
                replaces = [kw for kw in v_node.keywords if kw.arg == "replaces"]
                for rel_kw in upgrades + replaces:
                    if not isinstance(rel_kw.value, List):
                        # TODO: Add error code for this
                        self._show_error_if_collecting(
                            w,
                            msg=f"Related versions must be declared as a list: {rel_kw.value}",
                            error_code=ErrorCode.undefined_version,
                        )
                        errors = True
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
                                errors = True
                                return

                            else:
                                if w.value not in [v.name for (v, _) in versions]:
                                    self._show_error_if_collecting(
                                        w,
                                        msg=f"Undefined version: {w.value}",
                                        error_code=ErrorCode.undefined_version,
                                    )
                                    errors = True

                                elif w.value == version.name:
                                    self._show_error_if_collecting(
                                        w,
                                        msg=f"Version {version.name} can not be related to itself.",
                                        error_code=ErrorCode.self_relation_version,
                                    )
                                    errors = True

                #     try:
                #         find_cycle(g)
                #         self._show_error_if_collecting(
                #             node, error_code=ErrorCode.cyclic_version_graph
                #         )
                #     except NetworkXNoCycle:
                #         pass
        if not errors:
            from vpy.lib.utils import graph

            g = graph(node)
            self.graph = versions
            try:
                cycle = find_cycle(g)
                self._show_error_if_collecting(
                    node,
                    f"Cycle detected in version graph: {cycle}",
                    ErrorCode.cyclic_version_graph,
                )
            except NetworkXNoCycle:
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
        except:
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
