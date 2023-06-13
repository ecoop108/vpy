import argparse
import logging
import os
from lib.utils import graph
from lib.lib_types import VersionId
import inspect
import ast
import importlib.util
from lib.slice import rw_module


def list_versions(file) -> set[VersionId]:

    spec = importlib.util.spec_from_file_location(file[:-3], file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module_ast = ast.parse(inspect.getsource(module))
    versions: set[VersionId] = set()
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            versions = versions.union({v.name for v in graph(node).nodes})
    return versions


def target(file, version: VersionId):
    if version not in list_versions(file):
        exit(f"Invalid target {version}")

    spec = importlib.util.spec_from_file_location(
        os.path.basename(file)[:-3], file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    slices = rw_module(module, version)
    print("\n".join(slices))


def argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--list",
                        help="List versions of a module",
                        action='store_true')
    parser.add_argument('-i', '--input', help='Input file name', required=True)
    parser.add_argument("-t",
                        "--target",
                        help="Extract code for a target version",
                        required=False)
    return parser


def cli_main():
    args = argparser().parse_args()
    logging.basicConfig(level=logging.INFO)

    if not os.path.isfile(args.input):
        exit("Missing input file.")

    if args.list:
        print("\n".join(list_versions(args.input)))
        exit()

    if args.target:
        target(args.input, VersionId(args.target))
        exit()
