"""Explicit guard for destructive downgrades on disposable databases."""

import os


def require_destructive_downgrade() -> None:
    """Prevent accidental removal of accepted facts in normal environments."""
    if os.getenv("REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError("Set REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE=1 for a test database")
