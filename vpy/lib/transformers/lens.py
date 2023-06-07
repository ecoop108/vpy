from ast import Attribute, FunctionDef, Name, arg, keyword
import copy
from vpy.lib.lib_types import VersionIdentifier
from vpy.lib.utils import has_get_lens, is_self_attribute, has_put_lens, is_lens, get_at
import ast


class FieldCollector(ast.NodeVisitor):

    def __init__(self, fields: set[str]):
        self.fields = fields
        self.references = set()

    def visit_Attribute(self, node):
        if is_self_attribute(node) and node.attr in self.fields:
            self.references.add(node.attr)
        self.visit(node.value)


class PutLens(ast.NodeTransformer):

    def __init__(self, fields: set[str]):
        self._fields = fields

    def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:
        visitor = FieldCollector(self._fields)
        visitor.visit(node)
        for f in visitor.references:
            node.args.kwonlyargs.append(arg(arg=f))
            node.args.kw_defaults.append(None)
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(
                    dec.func, ast.Name) and dec.func.id == 'get':
                dec.func.id = 'put'
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node) -> Attribute | Name:
        if is_self_attribute(node) and node.attr in self._fields:
            if isinstance(node.ctx, ast.Load):
                node = Name(id=node.attr, ctx=ast.Load())
        else:
            node.value = self.visit(node.value)
        return node


class LensTransformer(ast.NodeTransformer):

    def check_field_in_function(self, node, field: str):
        for child_node in ast.walk(node):
            #TODO: Get fields from other functions
            if isinstance(child_node, ast.Call):
                pass
            if isinstance(child_node, ast.Attribute):
                if is_self_attribute(child_node) and child_node.attr == field:
                    return True
        return False

    def __init__(self, cls_ast, bases: dict[VersionIdentifier,
                                            VersionIdentifier],
                 fields: dict[VersionIdentifier, set[str]],
                 lenses: dict[VersionIdentifier,
                              dict[VersionIdentifier,
                                   dict[str,
                                        FunctionDef]]], v: VersionIdentifier):
        self.cls_ast = cls_ast
        self.bases = bases
        self.fields = fields
        self.lenses = lenses
        self.v = v

    def visit_FunctionDef(self, node):
        if is_lens(node):
            return node
        self.target = get_at(node)
        if self.bases[self.target] == self.bases[self.v]:
            return node
        lenses = self.lenses[self.bases[self.target]][self.bases[self.v]]
        if lenses is not None:
            self.generic_visit(node)
        else:
            raise Exception(
                f'Missing lens from version {self.v} to version {self.target}')

        return node

    def rw_lens(self, target: ast.Attribute,
                value: ast.expr | None) -> list[ast.Expr]:
        exprs = []
        lenses_t_v = self.lenses[self.bases[self.target]][self.bases[self.v]]
        if lenses_t_v is not None:
            for field in lenses_t_v:
                lens_node = lenses_t_v[field]
                if self.check_field_in_function(lens_node, target.attr):
                    self_attr = Attribute(value=ast.Name(id='self',
                                                         ctx=ast.Load()),
                                          attr=lens_node.name,
                                          ctx=ast.Load())
                    if value:
                        args_visitor = FieldCollector(self.fields[self.target])
                        args_visitor.visit(lens_node)
                        args = args_visitor.references
                        rw_value = self.visit(value)
                        self_call = ast.Call(
                            func=self_attr,
                            args=[],
                            keywords=[
                                keyword(arg=target.attr, value=rw_value)
                            ] + [
                                keyword(arg=f,
                                        value=self.visit(
                                            ast.parse(f'self.{f}')))
                                for f in args if f != target.attr
                            ])

                        if not has_put_lens(self.cls_ast, lens_node):
                            put_lens = PutLens(self.fields[self.target]).visit(
                                copy.deepcopy(lens_node))
                            self.cls_ast.body.append(put_lens)
                        lens_target = Attribute(value=ast.Name(
                            id='self', ctx=ast.Store()),
                                                attr=field)
                        lens_assign = ast.Assign(targets=[lens_target],
                                                 value=self_call)
                        exprs.append(lens_assign)
        return [ast.Expr(value=e) for e in exprs]

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Attribute) and is_self_attribute(
                node.target) and node.target.attr in self.fields[self.target]:
            left_node = copy.deepcopy(node.target)
            left_node.ctx = ast.Load()
            unfold = ast.BinOp(left=left_node, right=node.value, op=node.op)
            assign = ast.Assign(targets=[node.target], value=unfold)
            return self.rw_lens(node.target, assign.value)
        if node.value:
            node.value = self.visit(node.value)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Attribute) and is_self_attribute(
                node.target) and node.target.attr in self.fields[self.target]:
            return self.rw_lens(node.target, node.value)
        if node.value:
            node.value = self.visit(node.value)
        return node

    def visit_Assign(self, node):
        exprs = []
        node.value = self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Attribute) and is_self_attribute(
                    target) and target.attr in self.fields[self.target]:
                exprs += self.rw_lens(target, node.value)
            elif isinstance(target, ast.Name):
                node_copy = copy.deepcopy(node)
                node_copy.targets = [target]
                exprs.append(node_copy)
            elif isinstance(target, ast.Tuple):
                assert (False)
            elif isinstance(target, ast.List):
                assert (False)
        return exprs

    def visit_Attribute(self, node):
        lenses_v_t = self.lenses[self.bases[self.v]][self.bases[self.target]]
        if is_self_attribute(node) and node.attr in self.fields[self.target]:
            if isinstance(node.ctx, ast.Load):
                if lenses_v_t is not None:
                    if node.attr in lenses_v_t:
                        lens_node = lenses_v_t[node.attr]
                        self_attr = ast.Attribute(value=ast.Name(
                            id='self', ctx=ast.Load()),
                                                  attr=lens_node.name,
                                                  ctx=ast.Load())

                        # Create the call node for "self.lens()"
                        self_call = ast.Call(func=self_attr,
                                             args=[],
                                             keywords=[])

                        # Add lens to class body if missing
                        if not has_get_lens(self.cls_ast, lens_node):
                            self.cls_ast.body.append(lens_node)
                        return self_call
                    else:
                        raise Exception(
                            f'Missing lens for field {node.attr} from version {self.v} to version {self.target}'
                        )
        return node
