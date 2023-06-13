import ast
from pyanalyze.ast_annotator import annotate_file
from pyanalyze.value import dump_value

tree = annotate_file("/home/lc/vfj/counter.py")
for n in ast.walk(tree):
    if isinstance(n, ast.Attribute):
        print(ast.unparse(n.value), dump_value(n.value.inferred_value))
