"""pages のテスト。表のページだけを 1ページの PDF に切り出せるかを確かめる。"""

import io
import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from llm_pdf_table_extractor.pages import extract_page

META_1_1 = Path("data/truth/1-1.meta.json")
PDF = Path("data/raw/26nihon.pdf")
NO_PDF = "PDF は mise run fetch で落とす（git の対象外）"


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    """幅が 100・200・300 の白紙 3ページの PDF（ページを幅で見分ける）。"""
    writer = PdfWriter()
    for width in (100, 200, 300):
        writer.add_blank_page(width=width, height=100)
    path = tmp_path / "three.pdf"
    with path.open("wb") as f:
        writer.write(f)
    return path


def test_extract_page_returns_only_that_page(three_page_pdf: Path) -> None:
    pages = PdfReader(io.BytesIO(extract_page(three_page_pdf, 2))).pages

    assert len(pages) == 1
    assert pages[0].mediabox.width == 200


@pytest.mark.parametrize("page_number", [0, 4])
def test_extract_page_rejects_page_out_of_range(
    three_page_pdf: Path, page_number: int
) -> None:
    with pytest.raises(ValueError, match="3 ページ"):
        extract_page(three_page_pdf, page_number)


@pytest.mark.skipif(not PDF.exists(), reason=NO_PDF)
def test_extract_page_of_table_1_1_has_its_title() -> None:
    meta = json.loads(META_1_1.read_text(encoding="utf-8"))
    page_number: int = meta["pdf_page"]

    pages = PdfReader(io.BytesIO(extract_page(PDF, page_number))).pages

    assert len(pages) == 1
    assert "都道府県別面積" in pages[0].extract_text()
