from ast import ClassDef, Constant, FunctionDef, List
from typing import TYPE_CHECKING

from networkx import NetworkXNoCycle, find_cycle
from vpy.typechecker.pyanalyze.node_visitor import (
    BaseNodeVisitor,
    Failure,
)
from vpy.typechecker.pyanalyze.value import CanAssignError, Value
from .name_check_visitor import ClassAttributeChecker, NameCheckVisitor
from .error_code import ErrorCode

if TYPE_CHECKING:
    from vpy.lib.lib_types import VersionId, Environment


class VersionCheckVisitor(BaseNodeVisitor):
    def visit_Module(self, node) -> Value:
        for cls in node.body:
            if isinstance(cls, ClassDef):
                self.visit_ClassDef(cls)
        if self.seen_errors:
            return

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
                self.show_error(
                    name.value,
                    msg=f"Version name must be a literal string: {name.value}",
                    # TODO: Create new error code for this
                    error_code=ErrorCode.duplicate_version,
                )
                return
            elif name.value.value in [w.name for (w, _) in versions[:idx]]:
                self.show_error(
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
                        self.show_error(
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
                                self.show_error(
                                    w,
                                    msg=f"Version names must be string literals",
                                    error_code=ErrorCode.undefined_version,
                                )
                                return

                            else:
                                if w.value not in [v.name for (v, _) in versions]:
                                    self.show_error(
                                        w,
                                        msg=f"Undefined version: {w.value}",
                                        error_code=ErrorCode.undefined_version,
                                    )
                                    return
                                elif w.value == version.name:
                                    self.show_error(
                                        w,
                                        msg=f"Version {version.name} can not be related to itself.",
                                        error_code=ErrorCode.self_relation_version,
                                    )
                                    return

        try:
            from vpy.lib.utils import graph

            g = graph(node)
            cycle = find_cycle(g)
            self.show_error(
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

    def visit_FunctionDef(self, node) -> Value:
        from vpy.lib.utils import get_at, get_decorators

        version_dec = (
            get_decorators(node, "at")
            + get_decorators(node, "get")
            + get_decorators(node, "put")
        )
        # TODO: Create error code for this
        if len(version_dec) == 0:
            self.show_error(node, "Missing version annotation")
            return
        if len(version_dec) > 1:
            self.show_error(node, "Multiple version annotations")
            return
        version_dec = version_dec[0]
        version = get_at(node)

        try:
            v = next(v for (v, _) in self.graph if v.name == version)
            return super().visit_FunctionDef(node)
        except StopIteration:
            self.show_error(
                version_dec,
                f"Undefined version: {version}",
                ErrorCode.undefined_version,
            )


class LensCheckVisitor(BaseNodeVisitor):

    def check(self) -> list[Failure]:
        from vpy.lib.utils import get_module_environment

        self.annotate = True
        version_check_visitor = VersionCheckVisitor(
            filename=self.filename,
            contents=self.contents,
            tree=self.tree,
            settings=self.settings,
        )
        version_check_visitor.check
        if version_check_visitor.all_failures:
            return version_check_visitor.all_failures
        kwargs = NameCheckVisitor.prepare_constructor_kwargs({})
        options = kwargs["checker"].options
        with ClassAttributeChecker(enabled=True, options=options) as attribute_checker:
            self.name_check_visitor = NameCheckVisitor(
                filename=self.filename,
                contents=self.contents,
                tree=self.tree,
                settings=self.settings,
                annotate=True,
                attribute_checker=attribute_checker,
                **kwargs,
            )
            # name_check_visitor.env = get_module_environment(self.tree)
            self.name_check_visitor.env = get_module_environment(self.tree)
            self.name_check_visitor.check()
            if self.name_check_visitor.all_failures:
                self.all_failures = self.name_check_visitor.all_failures
            return super().check()

    def visit_ClassDef(self, node) -> Value:
        from vpy.lib.utils import graph, get_class_environment, get_at
        from vpy.lib.lookup import _method_lookup
        from vpy.lib.lib_types import Graph

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
                    self.show_error(
                        m[0],
                        f"Conflicting definitions of method {m[0].name}: {v, [get_at(n) for n in m if get_at(n) != v]}",
                    )
                    return
                mver = get_at(m)
                mdef = _method_lookup(
                    Graph(graph=[v]),
                    node,
                    m.name,
                    v.name,
                )
                self.__check_missing_method_lens(m, mdef, cls_env)
                self.__check_missing_field_lens(m, mver, v.name, cls_env)

        method_lenses = cls_env.method_lenses

        for v, v_lenses in method_lenses.items():
            for method, m_lenses in v_lenses.items():
                for t, lens in m_lenses.items():
                    lens_node = lens.node
                    if lens_node is None:
                        continue
                    m_v = _method_lookup(
                        Graph(graph=[g.find_version(v)]),
                        node,
                        method,
                        v,
                    )
                    m_t = _method_lookup(
                        Graph(graph=[g.find_version(t)]),
                        node,
                        method,
                        t,
                    )
                    if m_v is not None and m_t is not None:
                        # Check that signature of method and lens match
                        self.__check_lens_method_signature(lens_node, m_v, v, t)

    def __check_missing_field_lens(self, m: FunctionDef, mver, v, cls_env):
        if mver != v and mver not in cls_env.bases[v]:
            for field in cls_env.fields[mver]:
                if (
                    field.name not in cls_env.get_lenses[mver]
                    or v.name not in cls_env.get_lenses[mver][field.name]
                ):
                    self.show_error(
                        m,
                        f"No path for field {field.name} in method {m.name} between versions {mver} and {v.name}",
                    )

    def __check_missing_method_lens(
        self, m: FunctionDef, mdef: FunctionDef, cls_env: "Environment"
    ):
        """Check for missing method lens between the introduced definition `mdef` and its corresponding versioned definition `m` (which will be used by clients in the context of get_at(m))"""
        from vpy.lib.lookup import get_at

        mdef_v = get_at(mdef)
        m_v = get_at(m)
        if mdef is not None and mdef_v != m_v:
            mdef_sig = self.name_check_visitor.visit(mdef).signature
            m_sig = self.name_check_visitor.visit(m).signature
            if (
                cls_env.method_lenses.find_lens(
                    v_from=mdef_v, v_to=m_v, field_name=m.name
                )
                is None
            ):
                if isinstance(
                    mdef_sig.can_assign(m_sig, self.name_check_visitor), CanAssignError
                ):
                    self.show_error(
                        m,
                        f"""Missing lens from version {mdef_v}: signatures do not match""",
                    )

    def __check_lens_method_signature(self, lens: FunctionDef, m: FunctionDef, v, t):
        lens_sig = self.name_check_visitor.visit(lens).signature
        m_sig = self.name_check_visitor.visit(m).signature
        # TODO: Check that lens has self and f parameters
        if "f" in lens_sig.parameters:
            del lens_sig.parameters["f"]
        if isinstance(
            lens_sig.can_assign(m_sig, self.name_check_visitor), CanAssignError
        ):
            self.show_error(
                lens,
                f"""Wrong signature in lens of method {m.name} from version {v} to {t}. The signature must match that of {m.name} in version {v}:
    def {lens.name}(self, f: Callable, {','.join(f"{p.name}: {p.annotation.simplify()}" for p in list(m_sig.parameters.values())[1:])}) -> {str(m_sig.return_value)}""",
            )

    #     lens_params = list(lens_sig.parameters.values())[2:]
    #     m_params = list(m_sig.parameters.values())[1:]
    #     if len(lens_params) != len(m_params):
    #         self.show_error(
    #             lens,
    #             f"""Wrong signature in lens of method {m.name} from version {v} to {t}. The signature must match that of {m.name} in version {v}:
    # def {lens.name}(self, f: Callable, {','.join(f"{p.name}: {p.annotation.simplify()}" for p in list(m_sig.parameters.values())[1:])}) -> {str(m_sig.return_value)}""",
    #         )
    #     else:
    #         for p0, p1, pn in zip(lens_params, m_params, lens.args.args[2:]):
    #             if p0.annotation.is_assignable(p1.annotation, self.name_check_visitor):
    #                 self.show_error(
    #                     pn,
    #                     f"""Incompatible type for argument {p0.name} in signature of lens for method {m.name} from version {v} to {t}. The signature must match that of {m.name} in version {v}:
    # def {lens.name}(self, f: Callable, {','.join(f"{p.name}: {p.annotation.simplify()}" for p in list(m_sig.parameters.values())[1:])}) -> {str(m_sig.return_value)}""",
    #                 )
    #     if lens_sig.return_value.is_assignable(
    #         m_sig.return_value, self.name_check_visitor
    #     ):
    #         self.show_error(
    #             lens_sig,
    #             f"""Incompatible return type in signature of lens for method {m.name} from version {v} to {t}. The signature must match that of {m.name} in version {v}:
    # def {lens.name}(self, f: Callable, {','.join(f"{p.name}: {p.annotation.simplify()}" for p in list(m_sig.parameters.values())[1:])}) -> {str(m_sig.return_value)}""",
    #         )
