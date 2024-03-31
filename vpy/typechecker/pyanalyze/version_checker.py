from ast import ClassDef, Constant, FunctionDef, List, Load, Store
from typing import TYPE_CHECKING

from networkx import NetworkXNoCycle, find_cycle
from vpy.typechecker.pyanalyze.node_visitor import (
    BaseNodeVisitor,
    Failure,
)
from vpy.typechecker.pyanalyze.value import CallableValue, CanAssignError, Value
from .name_check_visitor import ClassAttributeChecker, NameCheckVisitor
from .error_code import ErrorCode

if TYPE_CHECKING:
    from vpy.lib.lib_types import VersionId, ClassEnvironment, Graph


class VersionCheckVisitor(BaseNodeVisitor):
    def visit_Module(self, node):
        versions = set()
        for cls in node.body:
            # Visit class node and collect version definitions
            if isinstance(cls, ClassDef):
                self.visit_ClassDef(cls)
                versions = versions.union(self.graph)
            else:
                self.graph = versions
                self.visit(cls)
        if self.seen_errors:
            return

    def visit_ClassDef(self, node):
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
                    e=f"Version name must be a literal string: {name.value}",
                    # TODO: Create new error code for this
                    error_code=ErrorCode.duplicate_version,
                )
                return
            elif name.value.value in [w.name for (w, _) in versions[:idx]]:
                self.show_error(
                    name.value,
                    e=f"Duplicate version name: {name.value.value}",
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
                            e=f"Related versions must be declared as a list: {rel_kw.value}",
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
                                    e=f"Version names must be string literals",
                                    error_code=ErrorCode.undefined_version,
                                )
                                return

                            else:
                                if w.value not in [v.name for (v, _) in versions]:
                                    self.show_error(
                                        w,
                                        e=f"Undefined version: {w.value}",
                                        error_code=ErrorCode.undefined_version,
                                    )
                                    return
                                elif w.value == version.name:
                                    self.show_error(
                                        w,
                                        e=f"Version {version.name} can not be related to itself.",
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

    def visit_FunctionDef(self, node):
        from vpy.lib.utils import get_at, get_decorators

        at_dec = get_decorators(node, "at")
        get_dec = get_decorators(node, "get")
        put_dec = get_decorators(node, "put")
        run_dec = get_decorators(node, "run")
        version_dec = at_dec + get_dec + put_dec + run_dec
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
            next(v for (v, _) in self.graph if v.name == version)
        except StopIteration:
            self.show_error(
                version_dec,
                f"Undefined version: {version}",
                ErrorCode.undefined_version,
            )


class LensCheckVisitor(BaseNodeVisitor):
    error_code_enum = ErrorCode

    def check(self) -> list[Failure]:
        from vpy.lib.utils import get_module_environment

        version_check_visitor = VersionCheckVisitor(
            filename=self.filename,
            contents=self.contents,
            tree=self.tree,
            settings=self.settings,
        )
        version_check_visitor.check()
        if version_check_visitor.all_failures:
            self.all_failures = version_check_visitor.all_failures
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
            return self.name_check_visitor.all_failures
        self.env = get_module_environment(self.tree)
        self.visit(self.tree)
        attribute_checker.tree = self.tree
        return self.all_failures

    def visit_ClassDef(self, node):
        from vpy.lib.utils import graph, get_class_environment, get_decorators, get_at

        cls_env = get_class_environment(node)
        g = graph(node)
        # Check for method conflicts
        self.__check_method_conflicts(g, node, cls_env)

        method_lenses = cls_env.method_lenses

        for fun in (n for n in node.body if isinstance(n, FunctionDef)):
            lens_dec_node = get_decorators(fun, "get")
            if len(lens_dec_node) == 1:
                frm, to, attr = (a.value for a in lens_dec_node[0].args)
                if frm == to:
                    self.show_error(
                        lens_dec_node[0],
                        f"Lenses must be defined between different versions",
                    )
                    continue
                if attr not in [f.name for f in cls_env.fields[to]]:
                    m_to = next(
                        (m for m in cls_env.methods[to] if m.name == attr),
                        None,
                    )
                    if m_to is None:
                        self.show_error(
                            lens_dec_node[0],
                            f"Attribute {attr} is not defined in version {to} of this class",
                        )
                    elif (m_ver := get_at(m_to.interface)) != to:
                        self.show_error(
                            lens_dec_node[0],
                            f"No definition of method {attr} introduced in version {to}. Did you mean version {m_ver}?",
                        )
                    else:
                        m_frm = next(
                            (m for m in cls_env.methods[frm] if m.name == attr),
                            None,
                        )
                        if m_frm is None:
                            self.show_error(
                                lens_dec_node[0],
                                f"Attribute {attr} is not defined in version {frm} of this class",
                            )
                        elif (m_ver := get_at(m_frm.interface)) != frm:
                            self.show_error(
                                lens_dec_node[0],
                                f"No definition of method {attr} introduced in version {frm}. Did you mean version {m_ver}?",
                            )

        for v, v_lenses in method_lenses.items():
            for t, t_method_lenses in v_lenses.items():
                for method, lens in t_method_lenses.items():
                    lens_node = lens.node
                    if lens_node is None:
                        continue
                    m_v = next(
                        m.interface for m in cls_env.methods[v] if m.name == method
                    )
                    m_t = next(
                        m.interface for m in cls_env.methods[t] if m.name == method
                    )
                    if m_v is not None and m_t is not None:
                        # Check that signature of method and lens match
                        self.__check_lens_method_signature(lens_node, m_v, v, t)

    def __check_missing_field_lens(
        self,
        m: FunctionDef,
        v: "VersionId",
        cls_env: "ClassEnvironment",
    ):
        from vpy.lib.lookup import get_at
        from vpy.lib.visitors.fields import FieldNodeCollector

        mver = get_at(m)
        if mver != v and mver not in cls_env.bases[v]:
            ref_visitor = FieldNodeCollector(fields=cls_env.fields[mver])
            ref_visitor.visit(m)
            for ref in ref_visitor.references:
                # Check if a get lens for this attribute exists
                if isinstance(ref.ref_node.ctx, Load):
                    if (
                        cls_env.get_lenses.find_lens(
                            v_from=v, v_to=mver, attr=ref.field.name
                        )
                        is None
                    ):
                        self.show_error(
                            m,
                            f"No path for field {ref.field.name} in method {m.name} between versions {v} and {mver}",
                        )
                elif isinstance(ref.ref_node.ctx, Store):
                    found = False
                    # Iterate all lenses to find references to this attribute
                    for lens in (
                        cls_env.get_lenses.get(mver, dict()).get(v, dict()).values()
                    ):
                        lens_ref_visitor = FieldNodeCollector(
                            fields=cls_env.fields[mver]
                        )
                        if lens.node is None:
                            continue
                        lens_ref_visitor.visit(lens.node)
                        if any(
                            r.field.name == ref.field.name
                            for r in lens_ref_visitor.references
                        ):
                            found = True
                            # If there are multiple attributes referenced in the lens, we need a get lens for each of
                            # those
                            if len(lens_ref_visitor.references) > 1:
                                other_refs = [
                                    r
                                    for r in lens_ref_visitor.references
                                    if r.field.name != ref.field.name
                                ]
                                for other_ref in other_refs:
                                    if (
                                        cls_env.get_lenses.find_lens(
                                            v_from=v,
                                            v_to=mver,
                                            attr=other_ref.field.name,
                                        )
                                        is None
                                    ):
                                        self.show_error(
                                            node=other_ref.node,
                                            e=f"No path for field {other_ref.field.name} in lens {lens.node.name} between versions {v} and {mver}",
                                        )
                    if not found:
                        self.show_error(
                            node=ref.node,
                            e=f"Assignment to field {ref.field.name} in method {m.name} of version {mver} has no side effects in version {v}",
                        )
                else:
                    assert False

    def __check_method_conflicts(
        self, g: "Graph", cls_ast: ClassDef, cls_env: "ClassEnvironment"
    ):
        from vpy.lib.lib_types import VersionedMethod
        from vpy.lib.lookup import get_at, is_lens

        for v in g.all():
            methods = {m for m in cls_env.methods[v.name]}
            lenses_methods = {
                VersionedMethod(
                    name=l.node.name, interface=l.node, implementation=l.node
                )
                for w in cls_env.get_lenses.get(v.name, {}).values()
                for l in w.values()
                if l.node is not None
            }
            for m in methods.union(lenses_methods):
                if not is_lens(m.implementation):
                    self.__check_missing_method_lens(
                        implementation=m.implementation,
                        interface=m.interface,
                        cls_env=cls_env,
                    )
                    self.__check_missing_field_lens(m.implementation, v.name, cls_env)

    def __check_missing_method_lens(
        self,
        interface: FunctionDef,
        implementation: FunctionDef,
        cls_env: "ClassEnvironment",
    ):
        """Check for missing method lens between the interface definition and its corresponding implementation (which will be used by clients in the context of get_at(m))"""
        from vpy.lib.lookup import get_at

        if interface is None:
            return
        mdef_v = get_at(interface)
        m_v = get_at(implementation)
        if mdef_v == m_v:
            return
        mdef_val = self.name_check_visitor.visit(interface)
        m_val = self.name_check_visitor.visit(implementation)
        if not isinstance(mdef_val, CallableValue) or not isinstance(
            m_val, CallableValue
        ):
            assert False
        if (
            cls_env.method_lenses.find_lens(
                v_from=mdef_v, v_to=m_v, attr=implementation.name
            )
            is None
        ):
            if isinstance(
                mdef_val.signature.can_assign(m_val.signature, self.name_check_visitor),
                CanAssignError,
            ):
                self.show_error(
                    implementation,
                    f"""Missing lens from version {mdef_v}: signatures do not match""",
                )

    def __check_lens_method_signature(self, lens: FunctionDef, m: FunctionDef, v, t):
        from vpy.lib.lookup import get_at

        lens_at = get_at(lens)
        lens_sig = self.name_check_visitor.signature_from_value(
            self.name_check_visitor.visit(lens)
        )
        m_sig = self.name_check_visitor.signature_from_value(
            self.name_check_visitor.visit(m)
        )
        # TODO: Check that lens has self and f parameters
        if "f" in lens_sig.parameters:
            del lens_sig.parameters["f"]
        if isinstance(
            lens_sig.can_assign(m_sig, self.name_check_visitor), CanAssignError
        ) or isinstance(
            m_sig.can_assign(lens_sig, self.name_check_visitor), CanAssignError
        ):
            self.show_error(
                lens,
                f"""Wrong signature in lens of method {m.name} from version {v} to {t}. The signature must match that of {m.name} in version {v}:
    def {lens.name}(self, f: Callable, {','.join(f"{p.name}: {p.annotation.simplify()}" for p in list(m_sig.parameters.values())[1:])}) -> {str(m_sig.return_value)}""",
            )
