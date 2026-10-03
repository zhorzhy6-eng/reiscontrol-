"""Stage 0 end-to-end test discovery check."""

from pathlib import Path


def test_reference_documents_are_copied() -> None:
    root = Path(__file__).resolve().parents[2]
    assert list((root / "docs/01-requirements").glob("*.docx"))
    assert list((root / "docs/02-architecture").glob("*.docx"))
