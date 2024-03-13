from ast import ClassDef, Call, Name

from networkx import NetworkXNoCycle, find_cycle
from vpy.typechecker.pyanalyze.value import Value
from .name_check_visitor import NameCheckVisitor
from .error_code import ErrorCode


class VersionCheckVisitor(NameCheckVisitor):
    def visit_ClassDef(self, node) -> Value:

        # TODO: Iterate over the decorator nodes instead of the version graph.
        # The graph should only be created **after** these checks are complete.
        from vpy.lib.utils import get_decorators
        from vpy.lib.lib_types import Version

        version_dec = get_decorators(node, "version")
        versions = [(Version(d.keywords), d) for d in version_dec]
        for idx, (version, v_node) in enumerate(versions):
            if version.name in [w.name for (w, _) in versions[:idx]]:
                self._show_error_if_checking(
                    v_node,
                    msg=f"Duplicate version definition: {version.name}",
                    error_code=ErrorCode.duplicate_version,
                )
            if version.name in version.replaces:
                self._show_error_if_checking(
                    v_node,
                    msg=f"Version {version.name} can not replace itself.",
                    error_code=ErrorCode.self_replace_version,
                )
            if version.name in version.upgrades:
                self._show_error_if_checking(
                    node,
                    msg=f"Version {version.name} can not upgrade itself.",
                    error_code=ErrorCode.self_upgrade_version,
                )

            for rel_kw in (
                kw for kw in v_node.keywords if kw.arg in ("replaces", "upgrades")
            ):
                for w in rel_kw.value.elts:
                    if w.value not in [version.name for (v, _) in versions]:
                        self._show_error_if_checking(
                            w,
                            msg=f"Undefined version: {w.value}",
                            error_code=ErrorCode.undefined_version,
                        )

            for w in version.replaces + version.upgrades:
                if w not in [version.name for (v, _) in versions]:
                    self._show_error_if_checking(
                        v_node,
                        msg=f"Undefined version: {w}",
                        error_code=ErrorCode.undefined_version,
                    )

        # if node.name in self.env.versions:
        #     g = self.env.versions[node.name]
        #     versions = g.all()
        #     for idx, v in enumerate(versions):
        #         if v.name in [w.name for w in versions[:idx]]:
        #             self._show_error_if_checking(
        #                 node,
        #                 msg=f"Duplicate version definition: {v.name}",
        #                 error_code=ErrorCode.duplicate_version,
        #             )
        #     for v in versions:
        #         if v.name in v.replaces:
        #             self._show_error_if_checking(
        #                 node,
        #                 msg=f"Version {v.name} can not replace itself.",
        #                 error_code=ErrorCode.self_replace_version,
        #             )
        #         if v.name in v.upgrades:
        #             self._show_error_if_checking(
        #                 node,
        #                 msg=f"Version {v.name} can not upgrade itself.",
        #                 error_code=ErrorCode.self_upgrade_version,
        #             )
        #         for w in v.replaces + v.upgrades:
        #             if w not in [v.name for v in versions]:
        #                 self._show_error_if_checking(
        #                     node,
        #                     msg=f"Undefined version: {w}",
        #                     error_code=ErrorCode.undefined_version,
        #                 )
        #     try:
        #         find_cycle(g)
        #         self._show_error_if_checking(
        #             node, error_code=ErrorCode.cyclic_version_graph
        #         )
        #     except NetworkXNoCycle:
        #         pass

        return super().visit_ClassDef(node)

    def visit_FunctionDef(self, node) -> Value:
        return super().visit_FunctionDef(node)
