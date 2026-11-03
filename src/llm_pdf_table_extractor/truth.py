"""正解データ（1行 = 1セルの縦長の形）を読み書きし、xlsx から作る。

形の決めごとは decisions/0002。
"""

import csv
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

TRUTH_DIR = Path("data/truth")
CSV_HEADER = (
    "table_id",
    "row_label",
    "column_label",
    "value",
    "unit",
    "notes",
)


@dataclass(frozen=True)
class Cell:
    """表のセル 1つ。

    Attributes:
        table_id: 表の番号（例: "1-1"）。
        row_label: 行の見出し（表に書かれたまま）。
        column_label: 列の見出し（単位は外す）。
        value: 値。数値は桁区切りを外した文字列。記号（"-" など）はそのまま。
        unit: 単位。
        notes: そのセルにかかる注記の番号。
    """

    table_id: str
    row_label: str
    column_label: str
    value: str
    unit: str
    notes: tuple[str, ...] = ()


def write_cells(cells: list[Cell], path: Path) -> None:
    """セルを CSV に書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for cell in cells:
            writer.writerow(
                [
                    cell.table_id,
                    cell.row_label,
                    cell.column_label,
                    cell.value,
                    cell.unit,
                    ";".join(cell.notes),
                ]
            )


def read_cells(path: Path) -> list[Cell]:
    """CSV からセルを読む。"""
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Cell(
                table_id=row["table_id"],
                row_label=row["row_label"],
                column_label=row["column_label"],
                value=row["value"],
                unit=row["unit"],
                notes=tuple(n for n in row["notes"].split(";") if n),
            )
            for row in csv.DictReader(f)
        ]


def format_number(value: float, number_format: str) -> str:
    """数値を、xlsx の表示形式の小数の桁で、桁区切りなしの文字列にする。

    Args:
        value: セルの数値。
        number_format: セルの表示形式（例: "#,##0.00"）。

    Returns:
        例: 1000 と "#,##0.00" なら "1000.00"。
    """
    positive_part = number_format.split(";")[0]
    match = re.search(r"\.(0+)", positive_part)
    decimals = len(match.group(1)) if match else 0
    return f"{value:.{decimals}f}"


def _note_numbers(mark: object) -> tuple[str, ...]:
    """注記の印（"1)" など）から番号を取り出す。"""
    if mark is None:
        return ()
    return tuple(re.findall(r"(\d+)\)", str(mark)))


# 表 1-1: 「都道府県・注記・面積・千分比」の組が横に 3つ並ぶ。
# データは 7〜22 行目。
# 24 行目には表 1-2 の値（「三重, 540」）が混ざっているので読まない。
_TABLE_1_1_BLOCKS = (
    ("A", "B", "C", "D"),
    ("F", "G", "H", "I"),
    ("J", "K", "L", "M"),
)
_TABLE_1_1_ROWS = range(7, 23)


def build_table_1_1(xlsx_path: Path) -> list[Cell]:
    """表 1-1（都道府県別面積）の xlsx から正解のセルを作る。

    並びは PDF を読む順（左の組の上から下、次に中の組、右の組）。

    Args:
        xlsx_path: 統計局の表 1-1 の xlsx。

    Returns:
        行の見出しごとに「面積」「千分比」の 2セル。
    """
    sheet = load_workbook(xlsx_path).worksheets[0]
    cells: list[Cell] = []
    for name_col, note_col, area_col, ratio_col in _TABLE_1_1_BLOCKS:
        for row in _TABLE_1_1_ROWS:
            name = sheet[f"{name_col}{row}"].value
            if name is None:
                continue
            row_label = str(name).strip()
            notes = _note_numbers(sheet[f"{note_col}{row}"].value)
            # 単位は PDF と xlsx の見出し（「(km2)」「(0/00)」）のまま
            for column_label, unit, col in (
                ("面積", "km2", area_col),
                ("千分比", "0/00", ratio_col),
            ):
                source = sheet[f"{col}{row}"]
                number = source.value
                if not isinstance(number, (int, float)):
                    raise ValueError(f"{col}{row} が数値ではない: {number!r}")
                cells.append(
                    Cell(
                        table_id="1-1",
                        row_label=row_label,
                        column_label=column_label,
                        value=format_number(number, source.number_format),
                        unit=unit,
                        notes=notes,
                    )
                )
    return cells


def main() -> int:
    """表 1-1 の正解を作り直す（`mise run truth`）。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cells = build_table_1_1(Path("data/xlsx/2026/n260100100.xlsx"))
    out = TRUTH_DIR / "1-1.csv"
    write_cells(cells, out)
    logger.info("%s に %d セルを書いた", out, len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
