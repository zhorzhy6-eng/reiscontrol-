"""Stage 0 integration-test environment check."""

from sqlalchemy import __version__ as sqlalchemy_version


def test_sqlalchemy_is_available() -> None:
    assert sqlalchemy_version.startswith("2.")
