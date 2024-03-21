import sys

from vpy.typechecker.pyanalyze.version_checker import (
    LensCheckVisitor,
)


def main() -> None:
    sys.exit(LensCheckVisitor.main())
    # with Profile() as profile:
    #     exit_code = LensCheckVisitor.main()
    #     Stats(profile).strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats()
    #     sys.exit(exit_code)


if __name__ == "__main__":
    main()
