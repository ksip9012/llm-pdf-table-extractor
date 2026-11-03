"""元データ（PDF・xlsx）の一覧を読み、落として sha256 で確かめる。

一覧は `data/sources.toml`。置き場所の決めごとは decisions/0001。
"""

import hashlib
import logging
import sys
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SOURCES_PATH = Path("data/sources.toml")


class ChecksumMismatchError(Exception):
    """落としたファイルの sha256 が、一覧と合わない。"""


@dataclass(frozen=True)
class Source:
    """元データ 1件。

    Attributes:
        name: 人が読む名前。
        url: 落とす元の URL。
        path: リポジトリの直下からの置き場所。
        sha256: ファイルの sha256（16進数）。
        committed: リポジトリに入れるファイルか。
    """

    name: str
    url: str
    path: Path
    sha256: str
    committed: bool


def load_sources(sources_path: Path = DEFAULT_SOURCES_PATH) -> list[Source]:
    """元データの一覧を読む。

    Args:
        sources_path: 一覧の TOML ファイル。

    Returns:
        一覧に書かれた順の元データ。
    """
    with sources_path.open("rb") as f:
        data = tomllib.load(f)
    return [
        Source(
            name=str(item["name"]),
            url=str(item["url"]),
            path=Path(str(item["path"])),
            sha256=str(item["sha256"]),
            committed=bool(item["committed"]),
        )
        for item in data["sources"]
    ]


def sha256_of(path: Path) -> str:
    """ファイルの sha256 を 16進数で返す。"""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(source: Source, root: Path = Path()) -> Path:
    """元データを落とし、sha256 を確かめる。

    既にあって sha256 が合えば、落とさない。

    Args:
        source: 落とす元データ。
        root: リポジトリの直下。`source.path` はここからの場所。

    Returns:
        置いたファイルの場所。

    Raises:
        ChecksumMismatchError: 落としたファイルの sha256 が一覧と合わない場合。
    """
    dest = root / source.path
    if dest.exists() and sha256_of(dest) == source.sha256:
        logger.info("あり: %s", source.path)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    logger.info("落とす: %s", source.url)
    with urllib.request.urlopen(source.url) as response, tmp.open("wb") as f:
        while chunk := response.read(1 << 16):
            f.write(chunk)
    actual = sha256_of(tmp)
    if actual != source.sha256:
        tmp.unlink()
        raise ChecksumMismatchError(
            f"{source.path} の sha256 が一覧と合わない: {actual}"
        )
    tmp.replace(dest)
    return dest


def main() -> int:
    """一覧の元データを全部落とす（`mise run fetch`）。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for source in load_sources():
        fetch(source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
