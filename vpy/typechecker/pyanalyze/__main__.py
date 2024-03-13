import sys

from vpy.typechecker.pyanalyze.name_check_visitor import NameCheckVisitor
from vpy.typechecker.pyanalyze.version_checker import VersionCheckVisitor


def main() -> None:
    sys.exit(VersionCheckVisitor.main())


if __name__ == "__main__":
    main()
