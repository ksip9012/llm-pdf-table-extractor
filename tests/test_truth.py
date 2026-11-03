"""truth のテスト。正解が xlsx と PDF に合っているかを確かめる。"""

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from llm_pdf_table_extractor.truth import (
    TABLES,
    TRUTH_DIR,
    Cell,
    build_table,
    format_number,
    read_cells,
    write_cells,
)

TRUTH_1_1 = Path("data/truth/1-1.csv")
META_1_1 = Path("data/truth/1-1.meta.json")
TRUTH_1_2 = Path("data/truth/1-2.csv")
META_1_2 = Path("data/truth/1-2.meta.json")
TRUTH_1_8 = Path("data/truth/1-8.csv")
META_1_8 = Path("data/truth/1-8.meta.json")
PDF = Path("data/raw/26nihon.pdf")
NO_PDF = "PDF は mise run fetch で落とす（git の対象外）"


@pytest.mark.parametrize(
    ("value", "number_format", "expected"),
    [
        (1000, "#,##0.00", "1000.00"),
        (28.1, "#,##0.00", "28.10"),
        (14125, "#,##0", "14125"),
        (-1.8, "#,##0.0", "-1.8"),
        (19, "#,##0.0", "19.0"),
        (23.9, "\\a\\)#,##0.0", "23.9"),
        # General は Excel と同じく値をそのまま書く（表 1-8 の千葉の 7月など）
        (28.8, "General", "28.8"),
        (3.5, "General", "3.5"),
        (14125, "General", "14125"),
        (6.0, "General", "6"),
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


@pytest.mark.parametrize("table_id", sorted(TABLES))
def test_build_table_matches_committed_truth(table_id: str) -> None:
    truth = read_cells(TRUTH_DIR / f"{table_id}.csv")

    assert build_table(TABLES[table_id]) == truth


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


@pytest.mark.skipif(not PDF.exists(), reason=NO_PDF)
def test_truth_1_1_units_appear_on_pdf_page() -> None:
    meta = json.loads(META_1_1.read_text(encoding="utf-8"))
    page_number: int = meta["pdf_page"]
    text = PdfReader(PDF).pages[page_number - 1].extract_text()

    units = {c.unit for c in read_cells(TRUTH_1_1)}

    assert units == {"km2", "0/00"}
    assert all(f"({u})" in text for u in units)


def test_truth_1_2_has_all_rows_without_stray_rows() -> None:
    cells = read_cells(TRUTH_1_2)
    labels = list(dict.fromkeys(c.row_label for c in cells))

    assert len(cells) == 98
    assert len(labels) == 49
    assert labels[0] == "全国"
    assert labels[-1] == "本州、四国、九州"
    # xlsx の 32行目の「三重, 540, -」は PDF にないので入れない
    assert "三重" not in labels
    assert {c.unit for c in cells} == {""}


def test_truth_1_2_column_note_is_on_every_cell_of_the_column() -> None:
    meta = json.loads(META_1_2.read_text(encoding="utf-8"))
    cells = read_cells(TRUTH_1_2)

    # 注記の印「1)」は列の見出し「島の数」に付いている（decisions/0005）
    assert {c.notes for c in cells if c.column_label == "島の数"} == {("1",)}
    assert {c.notes for c in cells if c.column_label != "島の数"} == {()}
    assert set(meta["notes"]) == {"1"}


def _as_printed(value: str) -> str:
    """正解の値を、PDF に書かれる形（整数は 3桁ごとのカンマ）にする。"""
    return value if value == "-" else f"{int(value):,}"


@pytest.mark.skipif(not PDF.exists(), reason=NO_PDF)
def test_truth_1_2_rows_appear_on_pdf_page() -> None:
    meta = json.loads(META_1_2.read_text(encoding="utf-8"))
    page_number: int = meta["pdf_page"]
    text = " ".join(
        PdfReader(PDF).pages[page_number - 1].extract_text().split()
    )
    rows: dict[str, list[str]] = {}
    for c in read_cells(TRUTH_1_2):
        rows.setdefault(c.row_label, []).append(_as_printed(c.value))

    # PDF では「北海道 1,473 -」のように、行の見出しのあとに値が並ぶ
    missing = [
        f"{label} {' '.join(values)}"
        for label, values in rows.items()
        if f"{label} {' '.join(values)}" not in text
    ]
    assert missing == []


def test_truth_1_8_has_47_stations_by_13_columns() -> None:
    cells = read_cells(TRUTH_1_8)
    labels = list(dict.fromkeys(c.row_label for c in cells))
    columns = list(dict.fromkeys(c.column_label for c in cells))

    assert len(cells) == 611
    assert len(labels) == 47
    assert labels[0] == "札幌"
    assert labels[-1] == "那覇"
    assert columns == ["平均", *(f"{m}月" for m in range(1, 13))]
    # 単位は列をまとめる見出し「気温（℃）」から読む
    assert {c.unit for c in cells} == {"℃"}


def test_truth_1_8_keeps_special_cells_as_printed() -> None:
    meta = json.loads(META_1_8.read_text(encoding="utf-8"))
    cells = {(c.row_label, c.column_label): c for c in read_cells(TRUTH_1_8)}

    # 表示形式が General のセルも、PDF のとおりの桁
    assert cells[("千葉", "7月")].value == "28.8"
    assert cells[("彦根", "12月")].value == "6.6"
    # 表示形式に入った「a)」（準正常値）は、そのセルの notes
    assert [k for k, c in cells.items() if c.notes] == [("那覇", "11月")]
    assert cells[("那覇", "11月")].notes == ("a",)
    assert set(meta["notes"]) == {"a"}


@pytest.mark.skipif(not PDF.exists(), reason=NO_PDF)
def test_truth_1_8_rows_appear_on_pdf_page() -> None:
    meta = json.loads(META_1_8.read_text(encoding="utf-8"))
    page_number: int = meta["pdf_page"]
    lines = PdfReader(PDF).pages[page_number - 1].extract_text().splitlines()
    rows: dict[str, list[str]] = {}
    for c in read_cells(TRUTH_1_8):
        printed = "".join(f"{n})" for n in c.notes) + c.value
        rows.setdefault(c.row_label, []).append(printed)

    # PDF では「那覇 24.4 … a)23.9 18.6」のように、官署ごとに 1行
    expected = [
        f"{label} {' '.join(values)}" for label, values in rows.items()
    ]
    assert [line for line in expected if line not in lines] == []
