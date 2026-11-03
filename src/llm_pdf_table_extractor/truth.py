"""正解データ（1行 = 1セルの縦長の形）を読み書きし、xlsx から作る。

形の決めごとは decisions/0002、列の見出しの注記は decisions/0005。
"""

import csv
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell as XlsxCell
from openpyxl.cell.cell import MergedCell

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


def _label(text: object) -> str:
    """見出しから注記の印と空白（改行を含む）を外す。

    例: "島の数\n          1)" は "島の数"、"本州、四国、\n九州" は
    "本州、四国、九州"。
    """
    return re.sub(r"\s+", "", re.sub(r"\d+\)", "", str(text)))


def _unit(text: object) -> str:
    """単位の行の文字（"(km2)" など）から、かっこと空白を外す。"""
    if text is None:
        return ""
    return re.sub(r"[\s()（）]", "", str(text))


def _value(cell: XlsxCell | MergedCell, coordinate: str) -> str:
    """値のセルを、正解の値の文字列にする。

    数値は表示形式の小数の桁で、桁区切りなしにする。記号「-」はそのまま。

    Raises:
        ValueError: 数値でも「-」でもない。
    """
    value = cell.value
    if isinstance(value, (int, float)):
        return format_number(value, cell.number_format)
    if isinstance(value, str) and value.strip() == "-":
        return "-"
    raise ValueError(f"{coordinate} が数値でも「-」でもない: {value!r}")


@dataclass(frozen=True)
class Block:
    """横に並ぶ組 1つの列。

    Attributes:
        label_col: 行の見出しの列。
        note_col: 行の注記の印の列（ない表は None）。
        value_cols: 値の列（左から順に）。
    """

    label_col: str
    note_col: str | None
    value_cols: tuple[str, ...]


@dataclass(frozen=True)
class SideBySideTable:
    """行の見出しと値の組が、横にいくつか並ぶ表の、xlsx での置き場所。

    列の見出し・単位・列の注記は、見出しの行と単位の行から読む。

    Attributes:
        table_id: 表の番号。
        xlsx: 統計局の表の xlsx。
        blocks: 横に並ぶ組（左から順に）。
        rows: データの行。
        header_row: 列の見出しの行。
        unit_row: 単位の行（ない表は None。単位は空になる）。
    """

    table_id: str
    xlsx: Path
    blocks: tuple[Block, ...]
    rows: range
    header_row: int
    unit_row: int | None = None


TABLES = {
    # 「都道府県・注記・面積・千分比」の組が横に 3つ並ぶ。
    # 24 行目には表 1-2 の値（「三重, 540」）が混ざっているので読まない。
    "1-1": SideBySideTable(
        table_id="1-1",
        xlsx=Path("data/xlsx/2026/n260100100.xlsx"),
        blocks=(
            Block("A", "B", ("C", "D")),
            Block("F", "G", ("H", "I")),
            Block("J", "K", ("L", "M")),
        ),
        rows=range(7, 23),
        header_row=4,
        unit_row=5,
    ),
    # 「都道府県・島の数・2府県にまたがる島の数」の組が横に 2つ並ぶ。
    # 注記の印「1)」は列の見出し（島の数）に付いている（decisions/0005）。
    # 32 行目の「三重, 540, -」は PDF にない（30 行目の三重県と重なる）ので
    # 読まない。
    "1-2": SideBySideTable(
        table_id="1-2",
        xlsx=Path("data/xlsx/2026/n260100200.xlsx"),
        blocks=(
            Block("A", None, ("C", "D")),
            Block("F", None, ("H", "I")),
        ),
        rows=range(6, 31),
        header_row=4,
    ),
}


def build_table(table: SideBySideTable) -> list[Cell]:
    """xlsx から、横に組が並ぶ表の正解のセルを作る。

    並びは PDF を読む順（左の組の上から下、次に右の組）。

    Args:
        table: 表の xlsx での置き場所。

    Returns:
        行の見出しごとに、値の列の数だけのセル。
    """
    sheet = load_workbook(table.xlsx).worksheets[0]
    cells: list[Cell] = []
    for block in table.blocks:
        columns = [
            (
                _label(sheet[f"{col}{table.header_row}"].value),
                _unit(
                    sheet[f"{col}{table.unit_row}"].value
                    if table.unit_row is not None
                    else None
                ),
                _note_numbers(sheet[f"{col}{table.header_row}"].value),
                col,
            )
            for col in block.value_cols
        ]
        for row in table.rows:
            name = sheet[f"{block.label_col}{row}"].value
            if name is None:
                continue
            row_notes = (
                _note_numbers(sheet[f"{block.note_col}{row}"].value)
                if block.note_col is not None
                else ()
            )
            for column_label, unit, column_notes, col in columns:
                notes = sorted({*row_notes, *column_notes}, key=int)
                cells.append(
                    Cell(
                        table_id=table.table_id,
                        row_label=_label(name),
                        column_label=column_label,
                        value=_value(sheet[f"{col}{row}"], f"{col}{row}"),
                        unit=unit,
                        notes=tuple(notes),
                    )
                )
    return cells


def main() -> int:
    """正解を作り直す（`mise run truth`）。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for table_id, table in TABLES.items():
        cells = build_table(table)
        out = TRUTH_DIR / f"{table_id}.csv"
        write_cells(cells, out)
        logger.info("%s に %d セルを書いた", out, len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
