"""truth のテスト。表 1-1 の正解が xlsx と PDF に合っているかを確かめる。"""

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from llm_pdf_table_extractor.truth import (
    Cell,
    build_table_1_1,
    format_number,
    read_cells,
    write_cells,
)

XLSX_1_1 = Path("data/xlsx/2026/n260100100.xlsx")
TRUTH_1_1 = Path("data/truth/1-1.csv")
META_1_1 = Path("data/truth/1-1.meta.json")
PDF = Path("data/raw/26nihon.pdf")
NO_PDF = "PDF は mise run fetch で落とす（git の対象外）"


@pytest.mark.parametrize(
    ("value", "number_format", "expected"),
    [
        (1000, "#,##0.00", "1000.00"),
        (28.1, "#,##0.00", "28.10"),
        (14125, "#,##0", "14125"),
        (3.5, "General", "4"),
    ],
)
def test_format_number_uses_decimals_of_number_format(
    value: float, number_format: str, expected: str
) -> None:
    assert format_number(value, number_format) == expected


def test_write_then_read_cells_keeps_notes(tmp_path: Path) -> None:
    cells = [
        Cell("1-1", "宮城県", "面積", "7282.30", "km2", ("1",)),
        Cell("1-1", "北海道", "面積", "83422.27", "km2"),
    ]
    path = tmp_path / "t.csv"

    write_cells(cells, path)

    assert read_cells(path) == cells


def test_build_table_1_1_matches_committed_truth() -> None:
    assert build_table_1_1(XLSX_1_1) == read_cells(TRUTH_1_1)


def test_truth_1_1_has_all_prefectures_without_stray_rows() -> None:
    cells = read_cells(TRUTH_1_1)
    labels = list(dict.fromkeys(c.row_label for c in cells))

    assert len(cells) == 96
    assert labels[0] == "全国"
    assert labels[1] == "北海道"
    assert labels[-1] == "沖縄県"
    assert len(labels) == 48
    # xlsx の 24行目に混ざっている表 1-2 の値（「三重, 540」）は入れない
    assert "三重" not in labels
    assert "540.00" not in {c.value for c in cells}


def test_truth_1_1_notes_are_defined_in_meta() -> None:
    meta = json.loads(META_1_1.read_text(encoding="utf-8"))
    cells = read_cells(TRUTH_1_1)
    used = {n for c in cells for n in c.notes}

    assert used == set(meta["notes"])
    assert len({c.row_label for c in cells if c.notes}) == 21


@pytest.mark.skipif(not PDF.exists(), reason=NO_PDF)
def test_truth_1_1_values_appear_on_pdf_page() -> None:
    meta = json.loads(META_1_1.read_text(encoding="utf-8"))
    page_number: int = meta["pdf_page"]
    page = PdfReader(PDF).pages[page_number - 1]
    text = page.extract_text()

    missing = [
        c
        for c in read_cells(TRUTH_1_1)
        if f"{float(c.value):,.2f}" not in text or c.row_label not in text
    ]
    assert missing == []
