from cProfile import Profile
from pstats import Stats
import sys

from vpy.typechecker.pyanalyze.version_checker import (
    LensCheckVisitor,
)


def main() -> None:
    # sys.exit(LensCheckVisitor.main())
    with Profile(builtins=False) as profile:
        exit_code = LensCheckVisitor.main()
        Stats(profile).strip_dirs().dump_stats("tmp.prof")
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
