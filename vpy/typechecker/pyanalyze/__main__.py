import sys

from vpy.typechecker.pyanalyze.name_check_visitor import NameCheckVisitor
from vpy.typechecker.pyanalyze.version_checker import (
    LensCheckVisitor,
    VersionCheckVisitor,
)


def main() -> None:
    sys.exit(LensCheckVisitor.main())


if __name__ == "__main__":
    main()
