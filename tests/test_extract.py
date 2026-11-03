"""extract のテスト。

実 API は呼ばず、偽のクライアントで、渡す中身と応答の読み方を確かめる。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from google import genai
from google.genai import types

from llm_pdf_table_extractor.extract import (
    CELLS_SCHEMA,
    build_prompt,
    extract_cells,
)
from llm_pdf_table_extractor.pages import extract_page
from llm_pdf_table_extractor.truth import Cell

META_1_1 = Path("data/truth/1-1.meta.json")
PDF = Path("data/raw/26nihon.pdf")


@dataclass
class _FakeResponse:
    text: str | None
    usage_metadata: types.GenerateContentResponseUsageMetadata | None = None


@dataclass(frozen=True)
class _Call:
    model: str
    contents: list[types.Part | str]
    config: types.GenerateContentConfig


@dataclass
class _FakeModels:
    response_text: str | None
    calls: list[_Call] = field(default_factory=lambda: list[_Call]())

    def generate_content(
        self,
        *,
        model: str,
        contents: list[types.Part | str],
        config: types.GenerateContentConfig,
    ) -> _FakeResponse:
        self.calls.append(_Call(model, contents, config))
        return _FakeResponse(text=self.response_text)


@dataclass
class _FakeClient:
    models: _FakeModels


def _client(cells: list[dict[str, object]] | None) -> _FakeClient:
    text = None if cells is None else json.dumps({"cells": cells})
    return _FakeClient(_FakeModels(text))


_MIYAGI: dict[str, object] = {
    "row_label": "宮城県",
    "column_label": "面積",
    "value": "7282.30",
    "unit": "km2",
    "notes": ["1"],
}


def test_extract_cells_reads_cells_and_adds_table_id() -> None:
    client = _client([_MIYAGI])

    cells, _ = extract_cells(b"%PDF", "1-1", "都道府県別面積", client=client)

    assert cells == [Cell("1-1", "宮城県", "面積", "7282.30", "km2", ("1",))]


def test_extract_cells_sends_pdf_prompt_and_schema() -> None:
    client = _client([])

    extract_cells(
        b"%PDF-page", "1-1", "都道府県別面積", client=client, model="m"
    )

    call = client.models.calls[0]
    pdf_part, prompt = call.contents
    assert isinstance(pdf_part, types.Part)
    assert pdf_part.inline_data is not None
    assert pdf_part.inline_data.data == b"%PDF-page"
    assert pdf_part.inline_data.mime_type == "application/pdf"
    assert prompt == build_prompt("1-1", "都道府県別面積")
    assert call.model == "m"
    config = call.config
    assert config.response_mime_type == "application/json"
    assert config.response_schema is CELLS_SCHEMA


def test_extract_cells_fails_when_response_has_no_text() -> None:
    with pytest.raises(ValueError, match="本文がなかった"):
        extract_cells(b"%PDF", "1-1", "t", client=_client(None))


def test_prompt_names_table_but_not_truth_labels() -> None:
    prompt = build_prompt("1-1", "都道府県別面積（令和7年）")

    assert "表 1-1 都道府県別面積（令和7年）" in prompt
    # 正解の見出しは渡さない（decisions/0003）
    assert "北海道" not in prompt
    assert "千分比" not in prompt


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not PDF.exists() or "GOOGLE_CLOUD_PROJECT" not in os.environ,
    reason="PDF と Vertex AI の設定（GOOGLE_CLOUD_PROJECT など）が要る",
)
def test_extract_cells_of_table_1_1_with_real_api() -> None:
    meta = json.loads(META_1_1.read_text(encoding="utf-8"))
    page_pdf = extract_page(PDF, meta["pdf_page"])

    cells, _ = extract_cells(
        page_pdf, "1-1", meta["title"], client=genai.Client()
    )

    assert cells
    assert {c.table_id for c in cells} == {"1-1"}
