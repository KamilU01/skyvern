#!/usr/bin/env python3
"""Compatibility wrapper for the Skyvern fork migration repair utility."""

from skyvern.utils.fork_migration_repair import main


if __name__ == "__main__":
    raise SystemExit(main())
