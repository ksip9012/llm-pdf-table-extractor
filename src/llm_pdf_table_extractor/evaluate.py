"""LLM の出力と正解を、セルごとに比べる。

比べ方の決めごとは decisions/0004。
"""

import logging
import sys
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from llm_pdf_table_extractor.extract import OUTPUT_DIR
from llm_pdf_table_extractor.truth import TRUTH_DIR, Cell, read_cells

logger = logging.getLogger(__name__)

type Key = tuple[str, str]


def _normalize(text: str) -> str:
    """前後の空白を外し、NFKC で全角・半角を揃える。"""
    return unicodedata.normalize("NFKC", text).strip()


def _key(cell: Cell) -> Key:
    return (_normalize(cell.row_label), _normalize(cell.column_label))


def _plain(value: str) -> str:
    """値を NFKC で揃え、桁区切りのカンマを外す。"""
    return _normalize(value).replace(",", "")


def same_value(truth: str, output: str) -> bool:
    """値が同じか。どちらも数値として読めるなら数として比べる。

    例: "1,000.00" と "1000" は同じ。"-" と "-" は同じ。
    """
    a = _plain(truth)
    b = _plain(output)
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:
        return a == b


def same_digits(truth: str, output: str) -> bool:
    """値が小数の桁まで同じか（カンマを外した文字列として比べる）。

    例: "1,000.00" と "1000.00" は同じ。"1000.00" と "1000" は違う。
    """
    return _plain(truth) == _plain(output)


@dataclass(frozen=True)
class Mismatch:
    """食い違い 1つ。

    Attributes:
        key: 行の見出しと列の見出し。
        field: 違った項目（"value"・"digits"・"unit"・"notes"・"missing"・
            "extra"）。"digits" は、値は合っているが小数の桁が違う。
        truth: 正解の側の中身（"extra" では空）。
        output: 出力の側の中身（"missing" では空）。
    """

    key: Key
    field: str
    truth: str
    output: str


@dataclass(frozen=True)
class Report:
    """比べた結果。

    Attributes:
        truth_count: 正解のセルの数。
        output_count: 出力のセルの数。
        value_matches: 値が合ったセルの数。
        digit_matches: 値が小数の桁まで合ったセルの数。
        full_matches: 値（桁まで）・単位・注記がすべて合ったセルの数。
        mismatches: 食い違いの一覧。
    """

    truth_count: int
    output_count: int
    value_matches: int
    digit_matches: int
    full_matches: int
    mismatches: tuple[Mismatch, ...]

    @property
    def value_accuracy(self) -> float:
        """値の一致率（値が合ったセル ÷ 正解のセル）。"""
        if self.truth_count == 0:
            return 0.0
        return self.value_matches / self.truth_count

    def count(self, field: str) -> int:
        """ある項目の食い違いの数。"""
        return sum(1 for m in self.mismatches if m.field == field)


def compare(truth: list[Cell], output: list[Cell]) -> Report:
    """出力を正解と比べる。

    セルは行の見出しと列の見出しの組で対応させる。出力に同じ組が
    2回以上出たときは、最初のものを使い、残りは余計なセルとする。
    """
    found: dict[Key, Cell] = {}
    mismatches: list[Mismatch] = []
    for cell in output:
        key = _key(cell)
        if key in found:
            mismatches.append(Mismatch(key, "extra", "", cell.value))
        else:
            found[key] = cell

    truth_keys: set[Key] = set()
    value_matches = 0
    digit_matches = 0
    full_matches = 0
    for t in truth:
        key = _key(t)
        truth_keys.add(key)
        o = found.get(key)
        if o is None:
            mismatches.append(Mismatch(key, "missing", t.value, ""))
            continue
        ok = True
        if same_value(t.value, o.value):
            value_matches += 1
            if same_digits(t.value, o.value):
                digit_matches += 1
            else:
                ok = False
                mismatches.append(Mismatch(key, "digits", t.value, o.value))
        else:
            ok = False
            mismatches.append(Mismatch(key, "value", t.value, o.value))
        if _normalize(t.unit) != _normalize(o.unit):
            ok = False
            mismatches.append(Mismatch(key, "unit", t.unit, o.unit))
        if set(t.notes) != set(o.notes):
            ok = False
            mismatches.append(
                Mismatch(key, "notes", ";".join(t.notes), ";".join(o.notes))
            )
        if ok:
            full_matches += 1

    mismatches.extend(
        Mismatch(key, "extra", "", cell.value)
        for key, cell in found.items()
        if key not in truth_keys
    )
    return Report(
        truth_count=len(truth),
        output_count=len(output),
        value_matches=value_matches,
        digit_matches=digit_matches,
        full_matches=full_matches,
        mismatches=tuple(mismatches),
    )


def format_report(table_id: str, report: Report) -> str:
    """比べた結果を、人が読む文字列にする。"""
    lines = [
        f"表 {table_id}: 正解 {report.truth_count} セル"
        f" / 出力 {report.output_count} セル",
        f"値の一致率: {report.value_accuracy:.1%}"
        f"（{report.value_matches} / {report.truth_count}）",
        f"桁まで合ったセル: {report.digit_matches}",
        f"すべて合ったセル: {report.full_matches}",
        "食い違い: "
        + "・".join(
            f"{field} {report.count(field)}"
            for field in (
                "value",
                "digits",
                "unit",
                "notes",
                "missing",
                "extra",
            )
        ),
    ]
    for m in report.mismatches:
        row_label, column_label = m.key
        lines.append(
            f"  - [{m.field}] {row_label} / {column_label}:"
            f" 正解 {m.truth!r} / 出力 {m.output!r}"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """data/output/ の出力を正解と比べる（`mise run evaluate`）。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    table_id = argv[0] if argv else "1-1"
    report = compare(
        read_cells(TRUTH_DIR / f"{table_id}.csv"),
        read_cells(OUTPUT_DIR / f"{table_id}.csv"),
    )
    logger.info("%s", format_report(table_id, report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
