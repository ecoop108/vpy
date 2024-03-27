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
    BinOp,
    Call,
    ClassDef,
    Delete,
    Expr,
    For,
    List,
    Load,
    Name,
    NodeVisitor,
    Raise,
    Return,
    Store,
    Subscript,
    Try,
    TryStar,
    Tuple,
    While,
    With,
    expr,
    walk,
)
from typing import Any

from vpy.lib.lib_types import Environment, Graph, VersionId
from vpy.lib.utils import (
    annotation_from_type_value,
    fresh_var,
    is_field,
    set_typeof_node,
    typeof_node,
)


class RewriteName(ast.NodeTransformer):
    def __init__(self, src: AST, target: AST):
        self.src = src
        self.target = target

    def visit_Attribute(self, node):
        if node == self.src:
            name = copy.deepcopy(self.target)
            set_typeof_node(name, typeof_node(node))
            node = name
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if isinstance(self.src, Name) and node.id == self.src.id:
            name = copy.deepcopy(self.target)
            set_typeof_node(name, typeof_node(node))
            node = name
        return node


class ExtractLocalVar(ast.NodeTransformer):
    def __init__(
        self,
        g,
        cls_ast: ClassDef,
        env: Environment,
        aliases: dict[expr, Attribute],
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
        val_field_visitor = FieldReplacementVisitor(self)
        if node.value:
            val_field_visitor.visit(node.value)
        val_replacements = val_field_visitor.fields

        if val_replacements:
            return self.visit(Assign(targets=[node.target], value=node.value))

        return node

    def visit_AugAssign(self, node: AugAssign) -> Any:
        value_field_visitor = FieldReplacementVisitor(self)
        value_field_visitor.visit(node.value)
        if value_field_visitor.fields:
            left_node = copy.deepcopy(node.target)
            left_node.ctx = ast.Load()
            assign = Assign(
                targets=[node.target],
                value=BinOp(left=left_node, right=node.value, op=node.op),
            )
            return self.visit(assign)

        return node

    def visit_For(self, node: For) -> Any:
        field_visitor = FieldReplacementVisitor(self)
        field_visitor.visit(node.iter)
        iter_replacements = field_visitor.fields
        expr_before = []
        expr_after = []

        assign_visitor = AssignAfterCall(
            self.g, self.cls_ast, self.env, self.aliases, self.v_from, iter_replacements
        )
        assign_visitor.visit(node.iter)

        for idx, (attr, var) in enumerate(iter_replacements.items()):
            if all(
                v != var for i, v in enumerate(iter_replacements.values()) if i < idx
            ):
                var_assign = Assign(targets=[var], value=attr)
                expr_before.append(var_assign)
            rw_visitor = RewriteName(attr, var)
            node.iter = rw_visitor.visit(node.iter)
        if assign_visitor.assignments:
            var = Name(fresh_var(), ctx=Store())
            expr_before.append(Assign(targets=[var], value=node.iter))
            node.iter = var
        for idx, assign in enumerate(assign_visitor.assignments):
            if all(
                v != assign for i, v in enumerate(assign_visitor.assignments) if i < idx
            ):
                expr_before.append(assign)

        node = replace_in_body(node, "body", self)
        node = replace_in_body(node, "orelse", self)

        for attr, var in iter_replacements.items():
            expr_after.append(Assign(targets=[attr], value=var))

        return expr_before + [node] + expr_after

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
        # expr_before = []
        # for target in node.targets:
        #     field_visitor = FieldReplacementVisitor(self)
        #     field_visitor.visit(target)
        #     replacements = field_visitor.fields
        #     for idx, (attr, var) in enumerate(replacements.items()):
        #         if all(
        #             v != var for i, v in enumerate(replacements.values()) if i < idx
        #         ):
        #             var_assign = Assign(targets=[var], value=attr)
        #             expr_before.append(var_assign)
        #         visitor = RewriteName(src=attr, target=var)
        #         target = visitor.visit(target)
        # return expr_before + [node]

    def visit_With(self, node: With) -> Any:
        assert False

    def visit_Raise(self, node: Raise) -> Any:
        assert False

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        assert False

    def visit_Return(self, node: Return) -> Any:
        expr_before = []
        if node.value is not None:
            field_visitor = FieldReplacementVisitor(self)
            field_visitor.visit(node.value)
            replacements = field_visitor.fields
            for idx, (attr, var) in enumerate(replacements.items()):
                if all(
                    v != var for i, v in enumerate(replacements.values()) if i < idx
                ):
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


class AssignAfterSideEffects(NodeVisitor):
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
        self.assignments: list[Assign] = []

    def visit_Attribute(self, node: Attribute):
        if isinstance(node.ctx, Load) and node in self.aliases:
            if self.aliases[node] in self.replacements:
                value = self.replacements[self.aliases[node]]
            elif node in self.replacements:
                value = self.replacements[node]
            else:
                return
            self.assignments.append(
                Assign(
                    targets=[self.aliases[node]],
                    value=value,
                )
            )
        else:
            self.visit(node.value)

    def visit_Tuple(self, node: Tuple):
        for el in node.elts:
            self.visit(el)

    def visit_List(self, node: List):
        for el in node.elts:
            self.visit(el)

    def visit_Subscript(self, node: Subscript) -> Any:
        self.visit(node.value)


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
        self.assignments: list[Assign] = []

    def visit_Call(self, node: Call) -> Any:
        collected_args: list[Attribute] = []
        for arg in node.args:
            if arg in self.aliases:
                if self.aliases[arg] not in collected_args:
                    collected_args.append(self.aliases[arg])
                    if self.aliases[arg] in self.replacements:
                        value = self.replacements[self.aliases[arg]]
                    elif arg in self.replacements:
                        value = self.replacements[arg]
                    else:
                        value = arg
                    self.assignments.append(
                        Assign(
                            targets=[self.aliases[arg]],
                            value=value,
                        )
                    )

        for kw_arg in node.keywords:
            if kw_arg.value in self.aliases:
                if self.aliases[kw_arg.value] not in collected_args:
                    collected_args.append(self.aliases[kw_arg.value])
                    if self.aliases[kw_arg.value] in self.replacements:
                        value = self.replacements[self.aliases[kw_arg.value]]
                    elif kw_arg.value in self.replacements:
                        value = self.replacements[kw_arg.value]
                    else:
                        value = kw_arg.value
                    self.assignments.append(
                        Assign(
                            targets=[self.aliases[kw_arg.value]],
                            value=value,
                        )
                    )
        if isinstance(node.func, Attribute):
            assignments = []
            for n in walk(node.func.value):
                if n in self.aliases:
                    if self.aliases[n] in self.replacements:
                        value = self.replacements[self.aliases[n]]
                    elif n in self.replacements:
                        value = self.replacements[n]
                    else:
                        value = n
                    assignments.append(
                        Assign(
                            targets=[self.aliases[n]],
                            value=value,
                        )
                    )
            self.assignments.extend(assignments[::-1])


class FieldReplacementVisitor(NodeVisitor):
    def __init__(self, visitor: ExtractLocalVar | AssignAfterCall):
        self.fields: dict[Attribute, Name] = {}
        self.visitor = visitor

    def visit_Attribute(self, node: Attribute) -> Any:
        if isinstance(node.ctx, Load):
            obj_type = annotation_from_type_value(typeof_node(node.value))
            if obj_type in self.visitor.env.fields and is_field(
                node,
                self.visitor.env.fields[obj_type][self.visitor.v_from],
            ):
                if node in self.visitor.aliases:
                    if self.visitor.aliases[node] in self.fields:
                        self.fields[node] = self.fields[self.visitor.aliases[node]]
                    else:
                        self.fields[node] = Name(id=fresh_var(), ctx=Load())
                else:
                    self.fields[node] = Name(id=fresh_var(), ctx=Load())
        self.generic_visit(node)
