"""Stage 0 unit-test infrastructure check."""

from pathlib import Path


def test_domain_directories_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "backend/domain/events/README.md").is_file()
    assert (root / "backend/domain/trips/README.md").is_file()
