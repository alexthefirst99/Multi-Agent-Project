"""Command-line entry point.

The implementation lives in :mod:`orchestrator.cli`.
"""

from orchestrator.cli import main, run_system

__all__ = ["main", "run_system"]


if __name__ == "__main__":
    raise SystemExit(main())
