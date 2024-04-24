import argparse
import json
import logging
import os
import ast
import importlib.util
from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.module import ModuleStrictTransformer, ModuleTransformer
from vpy.lib.transformers.toolkit import AddVersionTransformer
from vpy.lib.utils import parse_module, graph


# TODO: Refactor this code, read errors from namecheckvisitor
def graph_versions(file: str) -> dict[str, list]:
    spec = importlib.util.spec_from_file_location(file[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    with open(file) as f:
        module_ast = ast.parse("\n".join(f.readlines()))
    versions: dict[str, list] = {}
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            versions[node.name] = graph(node).tree()
    return versions


def list_versions(file: str) -> set[VersionId]:
    spec = importlib.util.spec_from_file_location(file[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    # module = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(module)
    with open(file) as f:
        module_ast = ast.parse("\n".join(f.readlines()))
    versions: set[VersionId] = set()
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            versions = versions.union({v.name for v in graph(node).all()})
    return versions


def target(file: str, version: VersionId, strict: bool = False):
    if version not in list_versions(file):
        exit(f"Invalid target {version}")
    spec = importlib.util.spec_from_file_location(os.path.basename(file)[:-3], file)
    if spec is None or spec.loader is None:
        exit(f"Error reading module from file {file}")
    mod_ast, visitor = parse_module(file)
    if visitor.all_failures != []:
        exit(1)
    if strict:
        mod_ast = ModuleStrictTransformer(version).visit(mod_ast)
    else:
        mod_ast = ModuleTransformer(version).visit(mod_ast)
    slices = [ast.unparse(ast.fix_missing_locations(mod_ast))]
    print("\n".join(slices))


def check(file: str):
    spec = importlib.util.spec_from_file_location(os.path.basename(file)[:-3], file)
    if spec is None or spec.loader is None:
        exit(f"Error reading module from file {file}")
    _, visitor = parse_module(file)
    if visitor.all_failures != []:
        return 0
    return 1


def argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l", "--list", help="List versions of a module", action="store_true"
    )
    parser.add_argument(
        "-g",
        "--graph",
        help="Print JSON-formatted version graph of a module",
        action="store_true",
    )
    parser.add_argument("-i", "--input", help="Input file name", required=True)
    parser.add_argument(
        "-t", "--target", help="Extract code for a target version", required=False
    )
    parser.add_argument(
        "-s",
        "--strict",
        help="Get explicit code of a version",
        action="store_true",
    )
    return parser


def cli_main():
    args = argparser().parse_args()
    logging.basicConfig(level=logging.INFO)

    if not os.path.isfile(args.input):
        exit("Missing input file.")

    if args.list:
        print("\n".join(list_versions(args.input)))
        exit()

    elif args.graph:
        print(json.dumps(graph_versions(args.input)))
        exit()

    if args.target:
        target(args.input, VersionId(args.target), strict=args.strict)
        exit()

    exit(check(args.input))
