import ast
import copy
from ast import (
    AnnAssign,
    Assert,
    Assign,
    AsyncFunctionDef,
    Attribute,
    AugAssign,
    Call,
    ClassDef,
    Delete,
    Expr,
    For,
    FunctionDef,
    Load,
    Name,
    NodeTransformer,
    NodeVisitor,
    Raise,
    Return,
    Store,
    Try,
    TryStar,
    While,
    With,
    alias,
    walk,
)
from typing import Any

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    FieldReferenceCollector,
    fresh_var,
    get_obj_attribute,
    has_get_lens,
    is_field,
    is_obj_attribute,
)
from vpy.lib.visitors.alias import AliasVisitor


class RewriteName(ast.NodeTransformer):
    def __init__(self, target: str):
        self.target = target

    def visit_Attribute(self, node):
        if isinstance(node, ast.Attribute) and is_obj_attribute(node):
            name = Name(id=self.target, ctx=ast.Load())
            name.inferred_value = node.inferred_value
            return name
        else:
            self.generic_visit(node)
            return node


class ExtractLocalVar(ast.NodeTransformer):
    def __init__(
        self,
        g,
        cls_ast: ClassDef,
        env: Environment,
        aliases: dict,
        v_from: VersionId,
        v_target: VersionId,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_target = v_target
        self.v_from = v_from
        self.aliases = aliases

    def visit_Assign(self, node: Assign) -> Any:
        expr_before = []
        expr_after = []
        for idx, expr in enumerate(list(node.targets)):
            replacements = fields_replacements(expr, self)
            assign_visitor = AssignAfterCall(
                g=self.g,
                cls_ast=self.cls_ast,
                env=self.env,
                v_from=self.v_from,
                replacements=replacements,
                aliases=self.aliases,
            )
            assign_visitor.visit(expr)
            for assgn in assign_visitor.assignments:
                expr_after.append(assgn)

            for attr, var in replacements.items():
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
                visitor = RewriteName(var.id)
                node.targets[idx] = visitor.visit(expr)

        replacements = fields_replacements(node.value, self)
        assign_visitor = AssignAfterCall(
            g=self.g,
            cls_ast=self.cls_ast,
            env=self.env,
            v_from=self.v_from,
            replacements=replacements,
            aliases=self.aliases,
        )
        assign_visitor.visit(node.value)
        for assgn in assign_visitor.assignments:
            expr_after.append(assgn)

        for attr, var in replacements.items():
            var_assign = Assign(targets=[var], value=attr)
            expr_before.append(var_assign)
            visitor = RewriteName(var.id)
            node.value = visitor.visit(node.value)

        return expr_before + [node] + expr_after

    def visit_AnnAssign(self, node: AnnAssign) -> Any:
        assert False

    def visit_AugAssign(self, node: AugAssign) -> Any:
        expr_before = []
        target_replacements = fields_replacements(node.target, self)
        for attr, var in target_replacements.items():
            var_assign = Assign(targets=[var], value=attr)
            expr_before.append(var_assign)
            visitor = RewriteName(var.id)
            node.target = visitor.visit(node.target)

        val_replacements = fields_replacements(node.value, self)
        for attr, var in val_replacements.items():
            var_assign = Assign(targets=[var], value=attr)
            expr_before.append(var_assign)
            visitor = RewriteName(var.id)
            node.value = visitor.visit(node.value)

        return node

    def visit_For(self, node: For) -> Any:
        assert False

    def visit_While(self, node: While) -> Any:
        assert False

    def visit_Try(self, node: Try) -> Any:
        assert False

    def visit_TryStar(self, node: TryStar) -> Any:
        assert False

    def visit_Assert(self, node: Assert) -> Any:
        assert False

    def visit_Delete(self, node: Delete) -> Any:
        assert False

    def visit_With(self, node: With) -> Any:
        assert False

    def visit_Raise(self, node: Raise) -> Any:
        assert False

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        assert False

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        assert False

    def visit_Return(self, node: Return) -> Any:
        expr_before = []
        replacements = fields_replacements(node.value, self)
        for attr, var in replacements.items():
            var_assign = Assign(targets=[var], value=attr)
            expr_before.append(var_assign)
            visitor = RewriteName(var.id)
            node.value = visitor.visit(node.value)
        return expr_before + [node]

    def visit_If(self, node):
        cond_replacements = fields_replacements(node.test, self)
        expr_before = []
        for attr, var in cond_replacements.items():
            var_assign = Assign(targets=[var], value=attr)
            expr_before.append(var_assign)
            visitor = RewriteName(var.id)
            node.test = visitor.visit(node.test)
        node = replace_in_body(node, "body", self)
        node = replace_in_body(node, "orelse", self)
        return expr_before + [node]


def replace_in_body(node, key: str, visitor: ExtractLocalVar):
    idx = 0
    stmts = list(getattr(node, key))
    for expr in stmts:
        if isinstance(expr, Expr):
            replacements = fields_replacements(expr, visitor)
            assign_visitor = AssignAfterCall(
                g=visitor.g,
                cls_ast=visitor.cls_ast,
                env=visitor.env,
                v_from=visitor.v_from,
                aliases=visitor.aliases,
                replacements=replacements,
            )
            assign_visitor.visit(expr)
            for assign in assign_visitor.assignments:
                getattr(node, key).insert(idx + 1, assign)
            for attr, var in replacements.items():
                var_assign = Assign(targets=[var], value=attr)
                getattr(node, key).insert(idx, var_assign)
                rw_visitor = RewriteName(var.id)
                getattr(node, key)[idx + 1] = rw_visitor.generic_visit(expr)
                idx += 2 + len(assign_visitor.assignments)
        else:
            expr_copy = copy.deepcopy(expr)
            nodes = visitor.visit(expr_copy)
            expr = expr_copy
            if isinstance(nodes, list):
                del getattr(node, key)[idx]
                new = getattr(node, key)[:idx] + nodes + getattr(node, key)[idx:]
                setattr(node, key, new)
                idx += len(nodes)
            else:
                getattr(node, key)[idx] = nodes
                idx += 1
    return node


def fields_replacements(node, visitor: ExtractLocalVar):
    fields = {}
    for attr in walk(node):
        if (
            isinstance(attr, Attribute)
            and is_obj_attribute(attr)
            and isinstance(attr.ctx, Load)
        ):
            if is_field(
                attr,
                visitor.env.fields[attr.value.inferred_value.get_type().__name__][
                    visitor.v_from
                ],
            ):
                fields[attr] = Name(id=fresh_var(), ctx=Load())
        # elif aliases and attr in visitor.aliases:
        #     if not (hasattr(attr, "ctx") and isinstance(attr.ctx, Store)):
        #         fields[visitor.aliases[attr][1]] = Name(id=fresh_var(), ctx=Load())
    return fields


class AssignAfterCall(NodeVisitor):
    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        aliases: dict,
        v_from: str,
        replacements,
    ):
        self.g = g
        self.cls_ast = cls_ast
        self.env = env
        self.v_from = v_from
        self.aliases = aliases
        self.replacements = replacements
        self.assignments = []

    def visit_Call(self, node: Call) -> Any:
        for arg in node.args:
            if arg in self.aliases:
                self.assignments.append(
                    Assign(
                        targets=[self.aliases[arg][1]],
                        value=arg,
                    )
                )
            else:
                fields = fields_replacements(
                    arg,
                    self,
                )
                if fields:
                    for field in fields:
                        self.assignments.append(
                            Assign(targets=[field], value=self.replacements[field])
                        )

        for kw_arg in node.keywords:
            if kw_arg.value in self.aliases:
                self.assignments.append(
                    Assign(
                        targets=[self.aliases[arg][1]],
                        value=kw_arg.value,
                    )
                )
            else:
                fields = fields_replacements(
                    kw_arg.value,
                    self,
                )
                for field in fields:
                    self.assignments.append(
                        Assign(targets=[field], value=self.replacements[field])
                    )
        if isinstance(node.func, Attribute):
            if node.func.value in self.aliases:
                self.assignments.append(
                    Assign(
                        targets=[self.aliases[node.func.value][1]],
                        value=node.func.value,
                    )
                )
            else:
                fields = fields_replacements(
                    node.func,
                    self,
                )
                for field in fields:
                    self.assignments.append(
                        Assign(targets=[field], value=self.replacements[field])
                    )
