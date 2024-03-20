from cProfile import Profile
from pstats import SortKey, Stats
import sys

from vpy.typechecker.pyanalyze.name_check_visitor import NameCheckVisitor
from vpy.typechecker.pyanalyze.version_checker import (
    LensCheckVisitor,
    VersionCheckVisitor,
)


def main() -> None:
    sys.exit(LensCheckVisitor.main())
    # with Profile() as profile:
    #     exit_code = LensCheckVisitor.main()
    #     Stats(profile).strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats()
    #     sys.exit(exit_code)


if __name__ == "__main__":
    main()
