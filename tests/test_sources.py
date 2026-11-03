"""sources のテスト。ネットにはつながず、file:// の URL で落とす。"""

import hashlib
from pathlib import Path

import pytest

from llm_pdf_table_extractor.sources import (
    ChecksumMismatchError,
    Source,
    fetch,
    load_sources,
)


def _source(src: Path, sha256: str) -> Source:
    return Source(
        name="テスト",
        url=src.as_uri(),
        path=Path("data/raw/sample.bin"),
        sha256=sha256,
        committed=False,
    )


def test_fetch_downloads_and_checks_sha256(tmp_path: Path) -> None:
    src = tmp_path / "origin.bin"
    src.write_bytes(b"hello")
    sha = hashlib.sha256(b"hello").hexdigest()

    dest = fetch(_source(src, sha), root=tmp_path / "repo")

    assert dest.read_bytes() == b"hello"


def test_fetch_raises_when_sha256_differs(tmp_path: Path) -> None:
    src = tmp_path / "origin.bin"
    src.write_bytes(b"hello")
    root = tmp_path / "repo"

    with pytest.raises(ChecksumMismatchError):
        fetch(_source(src, "0" * 64), root=root)

    assert not (root / "data/raw/sample.bin").exists()
    assert not (root / "data/raw/sample.bin.part").exists()


def test_fetch_skips_when_file_already_matches(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    dest = root / "data/raw/sample.bin"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    missing = tmp_path / "no-such-file.bin"

    assert fetch(_source(missing, sha), root=root) == dest


def test_load_sources_reads_repository_list() -> None:
    sources = load_sources(Path("data/sources.toml"))

    # 本全体の PDF だけを落として使い、表ごとの xlsx はリポジトリに入れる
    # （decisions/0001）
    assert [s.path for s in sources if not s.committed] == [
        Path("data/raw/26nihon.pdf")
    ]
    assert all(s.path.suffix == ".xlsx" for s in sources if s.committed)
    assert len(sources) == 11
    assert all(len(s.sha256) == 64 for s in sources)
