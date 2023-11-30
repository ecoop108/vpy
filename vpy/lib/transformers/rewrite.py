import ast
import copy
from ast import (
    AST,
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
    Load,
    Name,
    NodeVisitor,
    Raise,
    Return,
    Store,
    Try,
    TryStar,
    While,
    With,
    expr,
    walk,
)
from typing import Any

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    fresh_var,
    is_field,
)


class RewriteName(ast.NodeTransformer):
    def __init__(self, src: AST, target: AST):
        self.src = src
        self.target = target

    def visit_Attribute(self, node):
        if node == self.src:
            name = copy.deepcopy(self.target)
            name.inferred_value = node.inferred_value
            node = name
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if isinstance(self.src, Name) and node.id == self.src.id:
            name = copy.deepcopy(self.target)
            name.inferred_value = node.inferred_value
            node = name
        return node


class ExtractLocalVar(ast.NodeTransformer):
    def __init__(
        self,
        g,
        cls_ast: ClassDef,
        env: Environment,
        aliases: dict[expr, tuple[str, expr]],
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
        # for idx, expr in enumerate(list(node.targets)):
        #     field_visitor = FieldReplacementVisitor(self)
        #     field_visitor.visit(expr)
        #     replacements = field_visitor.fields

        #     assign_visitor = AssignAfterCall(
        #         g=self.g,
        #         cls_ast=self.cls_ast,
        #         env=self.env,
        #         v_from=self.v_from,
        #         replacements=replacements,
        #         aliases=self.aliases,
        #     )
        #     assign_visitor.visit(expr)
        #     for assgn in assign_visitor.assignments:
        #         expr_after.append(assgn)

        #     for attr, var in replacements.items():
        #         var_assign = Assign(targets=[var], value=attr)
        #         expr_before.append(var_assign)
        #         visitor = RewriteName(src=attr, target=var)
        #         node.targets[idx] = visitor.visit(expr)

        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.value)
        replacements = field_visitor.fields
        assign_visitor = AssignAfterCall(
            g=self.g,
            cls_ast=self.cls_ast,
            env=self.env,
            v_from=self.v_from,
            replacements=replacements,
            aliases=self.aliases,
        )
        assign_visitor.visit(node.value)
        for idx, assgn in enumerate(assign_visitor.assignments):
            if all(
                a.value != assgn.value
                for i, a in enumerate(assign_visitor.assignments)
                if i < idx
            ):
                expr_after.append(assgn)
        for idx, (attr, var) in enumerate(replacements.items()):
            if all(v != var for i, v in enumerate(replacements.values()) if i < idx):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            visitor = RewriteName(src=attr, target=var)
            node.value = visitor.visit(node.value)

        return expr_before + [node] + expr_after

    def visit_AnnAssign(self, node: AnnAssign) -> Any:
        assert False

    def visit_AugAssign(self, node: AugAssign) -> Any:
        expr_before = []
        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.target)
        target_replacements = field_visitor.fields

        for attr, var in target_replacements.items():
            if all(v != var for i, v in enumerate(replacements.values()) if i < idx):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            visitor = RewriteName(src=attr, target=var)
            node.target = visitor.visit(node.target)

        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.value)
        val_replacements = field_visitor.fields
        for attr, var in val_replacements.items():
            if all(v != var for i, v in enumerate(replacements.values()) if i < idx):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            visitor = RewriteName(src=attr, target=var)
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

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        assert False

    def visit_Return(self, node: Return) -> Any:
        expr_before = []
        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.value)
        replacements = field_visitor.fields
        for idx, (attr, var) in enumerate(replacements.items()):
            if all(v != var for i, v in enumerate(replacements.values()) if i < idx):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            visitor = RewriteName(src=attr, target=var)
            node.value = visitor.visit(node.value)
        return expr_before + [node]

    def visit_If(self, node):
        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.test)
        cond_replacements = field_visitor.fields
        expr_before = []
        assign_visitor = AssignAfterCall(
            self.g, self.cls_ast, self.env, self.aliases, self.v_from, cond_replacements
        )
        assign_visitor.visit(node.test)
        for idx, (attr, var) in enumerate(cond_replacements.items()):
            if all(
                v != var for i, v in enumerate(cond_replacements.values()) if i < idx
            ):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            visitor = RewriteName(attr, var)
            node.test = visitor.visit(node.test)
        if assign_visitor.assignments:
            var = Name(fresh_var(), ctx=Store())
            expr_before.append(Assign(targets=[var], value=node.test))
            node.test = var
        for idx, assign in enumerate(assign_visitor.assignments):
            if all(
                v != assign for i, v in enumerate(assign_visitor.assignments) if i < idx
            ):
                expr_before.append(assign)
        node = replace_in_body(node, "body", self)
        node = replace_in_body(node, "orelse", self)
        return expr_before + [node]

    def visit_FunctionDef(self, node):
        # v = FieldReplacementVisitor(self)
        # v.generic_visit(node)
        node = replace_in_body(node, "body", self)
        return node


def replace_in_body(node, key: str, visitor: ExtractLocalVar, r: dict | None = None):
    idx = 0
    stmts = list(getattr(node, key))
    # for i, (attr, var) in enumerate(r.items()):
    #     if all(v != var for j, v in enumerate(r.values()) if j < i):
    #         var_assign = Assign(targets=[var], value=attr)
    #         getattr(node, key).insert(idx, var_assign)
    #     rw_visitor = RewriteName(attr, var)
    #     getattr(node, key)[idx + 1] = rw_visitor.generic_visit(getattr(node, key))

    for expr in stmts:
        if isinstance(expr, Expr):
            field_visitor = FieldReplacementVisitor(visitor)
            field_visitor.visit(expr)
            replacements = field_visitor.fields
            if r is not None:
                replacements = r
            assign_visitor = AssignAfterCall(
                g=visitor.g,
                cls_ast=visitor.cls_ast,
                env=visitor.env,
                v_from=visitor.v_from,
                aliases=visitor.aliases,
                replacements=replacements,
            )
            assign_visitor.visit(expr)
            for i, (attr, var) in enumerate(replacements.items().__reversed__()):
                if all(
                    v != var
                    for j, v in enumerate(replacements.values().__reversed__())
                    if j < i
                ):
                    var_assign = Assign(targets=[var], value=attr)
                    getattr(node, key).insert(idx, var_assign)
                    idx += 1
                rw_visitor = RewriteName(attr, var)
                getattr(node, key)[idx] = rw_visitor.generic_visit(expr)
            for assign in assign_visitor.assignments:
                getattr(node, key).insert(idx + 1, assign)
            idx += len(assign_visitor.assignments) + 1
        else:
            # expr_copy = copy.deepcopy(expr)
            nodes = visitor.visit(expr)
            # expr = expr_copy
            if isinstance(nodes, list):
                del getattr(node, key)[idx]
                new = getattr(node, key)[:idx] + nodes + getattr(node, key)[idx:]
                setattr(node, key, new)
                idx += len(nodes)
            else:
                getattr(node, key)[idx] = nodes
                idx += 1
    return node


class AssignAfterCall(NodeVisitor):
    def __init__(
        self,
        g: Graph,
        cls_ast: ClassDef,
        env: Environment,
        aliases: dict,
        v_from: VersionId,
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
        collected_args: list[expr] = []
        for arg in node.args:
            if arg in self.aliases:
                if self.aliases[arg][1] not in collected_args:
                    collected_args.append(self.aliases[arg][1])
                    if self.aliases[arg][1] in self.replacements:
                        value = self.replacements[self.aliases[arg][1]]
                    elif arg in self.replacements:
                        value = self.replacements[arg]
                    else:
                        value = arg
                    self.assignments.append(
                        Assign(
                            targets=[self.aliases[arg][1]],
                            value=value,
                        )
                    )
            else:
                field_visitor = FieldReplacementVisitor(self)
                field_visitor.visit(arg)
                fields = field_visitor.fields
                if fields:
                    for field in fields:
                        if field in self.aliases and field not in collected_args:
                            collected_args.append(self.aliases[field][1])
                            self.assignments.append(
                                Assign(targets=[field], value=self.replacements[field])
                            )

        for kw_arg in node.keywords:
            if kw_arg.value in self.aliases:
                if self.aliases[kw_arg.value][1] not in collected_args:
                    collected_args.append(self.aliases[kw_arg.value][1])
                    if self.aliases[kw_arg.value][1] in self.replacements:
                        value = self.replacements[self.aliases[kw_arg.value][1]]
                    elif kw_arg.value in self.replacements:
                        value = self.replacements[kw_arg.value]
                    else:
                        value = kw_arg.value
                    self.assignments.append(
                        Assign(
                            targets=[self.aliases[kw_arg.value][1]],
                            value=value,
                        )
                    )
            else:
                field_visitor = FieldReplacementVisitor(self)
                field_visitor.visit(kw_arg.value)
                fields = field_visitor.fields

                for field in fields:
                    if field in self.aliases and field not in collected_args:
                        collected_args.append(self.aliases[field][1])
                        self.assignments.append(
                            Assign(targets=[field], value=self.replacements[field])
                        )
        if isinstance(node.func, Attribute):
            assignments = []
            for n in walk(node.func.value):
                if n in self.aliases:
                    if self.aliases[n][1] in self.replacements:
                        value = self.replacements[self.aliases[n][1]]
                    elif n in self.replacements:
                        value = self.replacements[n]
                    else:
                        value = node.func.value
                    assignments.append(
                        Assign(
                            targets=[self.aliases[n][1]],
                            value=value,
                        )
                    )
            if assignments:
                self.assignments.extend(assignments)
            else:
                field_visitor = FieldReplacementVisitor(self)
                field_visitor.visit(node.func)
                fields = field_visitor.fields
                for field in fields:
                    self.assignments.append(
                        Assign(targets=[field], value=self.replacements[field])
                    )


class FieldReplacementVisitor(NodeVisitor):
    def __init__(self, visitor: ExtractLocalVar | AssignAfterCall):
        self.fields = {}
        self.visitor = visitor

    def visit_Attribute(self, node: Attribute) -> Any:
        if isinstance(node.ctx, Load):
            obj_type = node.value.inferred_value.get_type()
            if (
                obj_type
                and obj_type.__name__ in self.visitor.env.fields
                and is_field(
                    node,
                    self.visitor.env.fields[obj_type.__name__][self.visitor.v_from],
                )
            ):
                if node in self.visitor.aliases:
                    if self.visitor.aliases[node][1] in self.fields:
                        self.fields[node] = self.fields[self.visitor.aliases[node][1]]
                    else:
                        self.fields[node] = Name(id=fresh_var(), ctx=Load())
                else:
                    self.fields[node] = Name(id=fresh_var(), ctx=Load())
            self.generic_visit(node)
