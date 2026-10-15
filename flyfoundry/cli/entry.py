"""Console entry point. The bounty subsystem is dispatched BEFORE the research CLI is imported, so it works on Windows and
without numpy (the research code imports numpy and, historically, the Unix-only `resource` module)."""
from __future__ import annotations

import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "bounty":
        from flyfoundry.bounty_factory.cli import main_bounty
        return main_bounty(argv[1:])
    from flyfoundry.cli.main import main as research_main
    return research_main(argv)


if __name__ == "__main__":
    sys.exit(main())
