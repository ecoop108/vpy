import argparse
import json
import logging
import os
import inspect
import ast
import importlib.util
from vpy.lib.lib_types import VersionId
from vpy.lib.transformers.module import ModuleStrictTransformer, ModuleTransformer
from vpy.lib.transformers.toolkit import AddVersionTransformer
from vpy.lib.utils import parse_module, graph


# TODO: Refactor this code, read errors from namecheckvisitor
def graph_versions(file) -> list[list[dict[str, list[dict]]]]:
    spec = importlib.util.spec_from_file_location(file[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module_ast = ast.parse(inspect.getsource(module))
    versions = {}
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            versions[node.name] = graph(node).tree()
    return versions


def list_versions(file) -> set[VersionId]:
    spec = importlib.util.spec_from_file_location(file[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module_ast = ast.parse(inspect.getsource(module))
    versions: set[VersionId | list] = set()
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            version_graph = graph(node)
            versions = versions.union({v.name for v in version_graph})
    return versions


def target(file, version: VersionId, strict=False):
    if version not in list_versions(file):
        exit(f"Invalid target {version}")
    spec = importlib.util.spec_from_file_location(os.path.basename(file)[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mod_ast, visitor = parse_module(module)
    if visitor.all_failures != []:
        return
    if strict:
        mod_ast = ModuleStrictTransformer(version).visit(mod_ast)
    else:
        mod_ast = ModuleTransformer(version).visit(mod_ast)
    slices = [ast.unparse(ast.fix_missing_locations(mod_ast))]
    print("\n".join(slices))


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
    parser.add_argument("--new", help="Create a new version")
    parser.add_argument("--upgrades", nargs="+", help="List of upgrades")
    parser.add_argument("--replaces", nargs="+", help="List of replaces")
    return parser


def new_version(
    file, replaces: list[VersionId] | None, upgrades: list[VersionId] | None, name: str
):
    if replaces is None:
        replaces = []
    if upgrades is None:
        upgrades = []
    if any(v not in list_versions(file) for v in replaces + upgrades):
        exit(f"Invalid target.")
    spec = importlib.util.spec_from_file_location(os.path.basename(file)[:-3], file)
    if spec is None or spec.loader is None:
        exit("Error reading module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mod_ast, _ = parse_module(module)
    mod_ast = AddVersionTransformer(name, replaces=replaces, upgrades=upgrades).visit(
        mod_ast
    )
    print(ast.unparse(ast.fix_missing_locations(mod_ast)))


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

    if args.new:
        new_version(args.input, args.replaces, args.upgrades, args.new)
