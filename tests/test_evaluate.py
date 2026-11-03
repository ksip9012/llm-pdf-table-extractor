"""evaluate のテスト。わざとずらした出力で、食い違いを数えられるか確かめる。"""

from dataclasses import replace
from pathlib import Path

import pytest

from llm_pdf_table_extractor.evaluate import (
    Mismatch,
    compare,
    format_report,
    same_digits,
    same_value,
)
from llm_pdf_table_extractor.truth import Cell, read_cells

TRUTH_1_1 = Path("data/truth/1-1.csv")

_ZENKOKU = Cell("1-1", "全国", "千分比", "1000.00", "0/00")
_MIYAGI = Cell("1-1", "宮城県", "面積", "7282.30", "km2", ("1",))
_HOKKAIDO = Cell("1-1", "北海道", "面積", "83422.27", "km2")
_TRUTH = [_ZENKOKU, _MIYAGI, _HOKKAIDO]


@pytest.mark.parametrize(
    ("truth", "output", "expected"),
    [
        ("1000.00", "1,000.00", True),
        ("1000.00", "1000", True),
        ("1000.00", "１０００．００", True),
        ("7282.30", "7282.03", False),
        ("-", "-", True),
        ("-", "0", False),
    ],
)
def test_same_value(truth: str, output: str, expected: bool) -> None:
    assert same_value(truth, output) is expected


@pytest.mark.parametrize(
    ("truth", "output", "expected"),
    [
        ("1000.00", "1,000.00", True),
        ("1000.00", "１０００．００", True),
        ("1000.00", "1000", False),
        ("28.10", "28.1", False),
        ("-", "-", True),
    ],
)
def test_same_digits(truth: str, output: str, expected: bool) -> None:
    assert same_digits(truth, output) is expected


def test_compare_counts_dropped_decimals_apart_from_value() -> None:
    report = compare(_TRUTH, [replace(_ZENKOKU, value="1000"), *_TRUTH[1:]])

    # 桁を落としても値の一致率は下げず、桁の食い違いとして別に数える
    assert report.value_matches == 3
    assert report.digit_matches == 2
    assert report.full_matches == 2
    assert report.mismatches == (
        Mismatch(("全国", "千分比"), "digits", "1000.00", "1000"),
    )


def test_compare_counts_all_matched_when_output_equals_truth() -> None:
    report = compare(_TRUTH, list(_TRUTH))

    assert report.value_accuracy == 1.0
    assert report.full_matches == 3
    assert report.mismatches == ()


def test_compare_counts_value_unit_and_notes_separately() -> None:
    output = [
        replace(_ZENKOKU, unit="‰"),
        replace(_MIYAGI, notes=()),
        replace(_HOKKAIDO, value="83422.72"),
    ]

    report = compare(_TRUTH, output)

    # 単位と注記の誤りは、値の一致率を下げない
    assert report.value_matches == 2
    assert report.full_matches == 0
    assert set(report.mismatches) == {
        Mismatch(("全国", "千分比"), "unit", "0/00", "‰"),
        Mismatch(("宮城県", "面積"), "notes", "1", ""),
        Mismatch(("北海道", "面積"), "value", "83422.27", "83422.72"),
    }


def test_compare_counts_missing_extra_and_duplicates() -> None:
    output = [
        _ZENKOKU,
        _ZENKOKU,
        replace(_MIYAGI, row_label="宮城"),
        _HOKKAIDO,
    ]

    report = compare(_TRUTH, output)

    assert report.value_matches == 2
    assert report.value_accuracy == pytest.approx(2 / 3)
    assert report.count("missing") == 1
    assert report.count("extra") == 2
    assert Mismatch(("宮城県", "面積"), "missing", "7282.30", "") in (
        report.mismatches
    )


def test_compare_normalizes_spaces_and_width_of_labels() -> None:
    truth = [replace(_MIYAGI, row_label="第1区")]
    output = [replace(_MIYAGI, row_label=" 第１区 ")]

    report = compare(truth, output)

    assert report.full_matches == 1


def test_format_report_lists_each_mismatch() -> None:
    report = compare(_TRUTH, [_ZENKOKU, replace(_HOKKAIDO, value="1")])

    text = format_report("1-1", report)

    assert "値の一致率: 33.3%（1 / 3）" in text
    assert "[missing] 宮城県 / 面積" in text
    assert "[value] 北海道 / 面積: 正解 '83422.27' / 出力 '1'" in text


def test_compare_truth_1_1_with_itself_is_all_matched() -> None:
    cells = read_cells(TRUTH_1_1)

    assert compare(cells, cells).full_matches == 96
