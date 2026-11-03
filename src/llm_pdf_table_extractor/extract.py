"""表のページを Gemini に読ませて、正解と同じ縦長の形のセルを出させる。

LLM と PDF の渡し方は decisions/0003、出す形は decisions/0002。
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Protocol

from google import genai
from google.genai import types

from llm_pdf_table_extractor.pages import extract_page
from llm_pdf_table_extractor.truth import TRUTH_DIR, Cell, write_cells

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
OUTPUT_DIR = Path("data/output")


class LLMResponse(Protocol):
    """`generate_content` の応答のうち、使う部分。"""

    @property
    def text(self) -> str | None: ...

    @property
    def usage_metadata(
        self,
    ) -> types.GenerateContentResponseUsageMetadata | None: ...


class LLMModels(Protocol):
    """`client.models` の形。"""

    def generate_content(
        self,
        *,
        model: str,
        contents: list[types.Part | str],
        config: types.GenerateContentConfig,
    ) -> LLMResponse: ...


class LLMClient(Protocol):
    """`google.genai.Client` のうち、使う部分の形。

    テストでは偽のクライアントを渡す。
    """

    @property
    def models(self) -> LLMModels: ...


# 0002 の列のうち、table_id はこちらで付けるので LLM には出させない
CELLS_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "cells": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "row_label": types.Schema(type=types.Type.STRING),
                    "column_label": types.Schema(type=types.Type.STRING),
                    "value": types.Schema(type=types.Type.STRING),
                    "unit": types.Schema(type=types.Type.STRING),
                    "notes": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                    ),
                },
                required=[
                    "row_label",
                    "column_label",
                    "value",
                    "unit",
                    "notes",
                ],
                property_ordering=[
                    "row_label",
                    "column_label",
                    "value",
                    "unit",
                    "notes",
                ],
            ),
        ),
    },
    required=["cells"],
)

# 正解の見出しや値は渡さない（decisions/0003）
_PROMPT_TEMPLATE = """\
この PDF のページにある「表 {table_id} {title}」を読み取り、\
表のセルを 1つずつ書き出してください。ページにほかの表があっても、\
表 {table_id} だけを対象にします。

書き方:
- 1つのセルを、行の見出し（row_label）・列の見出し（column_label）・\
値（value）・単位（unit）・注記（notes）で書く
- 行の見出しと列の見出しは、表に書かれたまま写す
- 列の見出しに単位が書かれていれば、単位は unit に書き、column_label からは外す
- 同じ見出しの組が横に並んでいる表は、組ごとに分けず、1つの表として書く
- 値は、数値なら桁区切りのカンマを外し、小数の桁は表に書かれたまま残す。\
「-」などの記号はそのまま写す
- 見出しに付いた注記の印（「1)」など）は見出しから外し、\
番号（「1」）を notes に書く。\
行の見出しに付いた注記は、その行のセルすべての notes に書く
- 表の上から下、左の組から右の組の順に書く
"""


def build_prompt(table_id: str, title: str) -> str:
    """表の番号と表題から、LLM に渡す指示を作る。"""
    return _PROMPT_TEMPLATE.format(table_id=table_id, title=title)


def parse_cells(response: LLMResponse, table_id: str) -> list[Cell]:
    """応答の JSON をセルの一覧にする。

    Raises:
        ValueError: 応答に本文がない（安全のための遮断などで空になる）。
    """
    if response.text is None:
        raise ValueError("Gemini の応答に本文がなかった")
    data: dict[str, Any] = json.loads(response.text)
    return [
        Cell(
            table_id=table_id,
            row_label=c["row_label"],
            column_label=c["column_label"],
            value=c["value"],
            unit=c["unit"],
            notes=tuple(c["notes"]),
        )
        for c in data["cells"]
    ]


def extract_cells(
    page_pdf: bytes,
    table_id: str,
    title: str,
    *,
    client: LLMClient,
    model: str = DEFAULT_MODEL,
) -> tuple[list[Cell], LLMResponse]:
    """1ページの PDF を Gemini に渡し、表のセルを出させる。

    Args:
        page_pdf: 表のページだけの PDF（`pages.extract_page` の戻り値）。
        table_id: 表の番号（例: "1-1"）。
        title: 表題（`meta.json` の `title`）。
        client: `google.genai.Client`。テストでは偽のクライアントを渡す。
        model: 使うモデル。

    Returns:
        セルの一覧と、トークン数を見るための応答。
    """
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=page_pdf, mime_type="application/pdf"),
            build_prompt(table_id, title),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CELLS_SCHEMA,
        ),
    )
    return parse_cells(response, table_id), response


def main(argv: list[str]) -> int:
    """表のセルを取り出して data/output/ に書く（`mise run extract`）。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    table_id = argv[0] if argv else "1-1"
    meta = json.loads(
        (TRUTH_DIR / f"{table_id}.meta.json").read_text(encoding="utf-8")
    )
    page_pdf = extract_page(Path(meta["pdf"]), meta["pdf_page"])

    started = time.perf_counter()
    cells, response = extract_cells(
        page_pdf, table_id, meta["title"], client=genai.Client()
    )
    elapsed = time.perf_counter() - started

    out = OUTPUT_DIR / f"{table_id}.csv"
    write_cells(cells, out)
    logger.info("%s に %d セルを書いた（%.1f 秒）", out, len(cells), elapsed)
    usage = response.usage_metadata
    if usage is not None:
        logger.info(
            "トークン: 入力 %s / 出力 %s / 思考 %s",
            usage.prompt_token_count,
            usage.candidates_token_count,
            usage.thoughts_token_count,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
