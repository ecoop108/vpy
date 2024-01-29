import ast


class RemoveDecoratorsTransformer(ast.NodeTransformer):
    REMOVE = ["at", "version", "get", "put", "run"]

    def visit_ClassDef(self, node):
        new_decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id not in self.REMOVE:
                    new_decorators.append(decorator)
        node.decorator_list = new_decorators
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        new_decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id not in self.REMOVE:
                    new_decorators.append(decorator)
        node.decorator_list = new_decorators
        return node
