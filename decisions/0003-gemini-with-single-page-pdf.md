# 0003. LLM は Vertex AI の gemini-3.8-flash にし、表のページだけを 1ページの PDF で渡す

- Status: Accepted
- Date: 2026-11-03

## Context
[0002](./0002-truth-as-long-cells.md) で正解の形を決めたので、PDF の表を LLM に読ませて、同じ形で出させる。決めることは 2つある。

1. どの LLM を使うか
2. PDF をどの形で渡すか

LLM は、Step1-A2（llm-structured-output-extractor）で Vertex AI 経由の Gemini を使っていて、認証（`gcloud auth application-default login` の ADC）と課金の設定ができている。Step1 では精度・料金・時間を同じモデルで比べた。

PDF の渡し方の候補は次の 3つ。

| 渡し方 | よいところ | 気になるところ |
|---|---|---|
| 表のページだけを 1ページの PDF にする | 文字の層と見た目の両方を LLM が使える。pypdf だけで切り出せる | スキャンした PDF（文字の層がない）と同じ条件ではない |
| ページを画像（PNG）にする | スキャンした PDF と同じ条件になる | 画像にするライブラリ（pypdfium2 など）が増える。解像度を決める必要がある |
| pypdf で文字だけ抜き出す | 安くて速い | 表 1-1 は「都道府県・面積・千分比」の組が横に 3つ並ぶので、抜き出すと列の関係が崩れやすい |

本全体の PDF（`data/raw/26nihon.pdf`）をそのまま渡すと、トークンが増えるうえ、LLM が表を探すところから始めることになる。

## Decision
LLM は Vertex AI の `gemini-3.8-flash` を使い、表のページだけを 1ページの PDF にして渡す。

- 認証は Step1-A2 と同じ ADC。`GOOGLE_GENAI_USE_VERTEXAI=true`・`GOOGLE_CLOUD_PROJECT`・`GOOGLE_CLOUD_LOCATION=global` の環境変数で Vertex AI を使う。モデルは `GEMINI_MODEL` で変えられるようにする
- 表のページは `<表の番号>.meta.json` の `pdf_page` から決め、pypdf でそのページだけの PDF を作って `application/pdf` で渡す
- 出力は Structured Output（`response_schema`）で、0002 と同じ列（`row_label`・`column_label`・`value`・`unit`・`notes`）のセルの一覧にする。`table_id` はこちらで決めて付ける
- プロンプトで LLM に伝えるのは、表の番号・表題と、0002 の値の書き方（桁区切りを外す、小数の桁は PDF のまま、単位は列の見出しから外す、注記は番号で書く）。正解の見出しや値は渡さない

## Consequences
- Step1 と同じモデル・認証なので、精度・料金・時間を Step1 の結果と並べて見られる
- 1つのページに複数の表が載っていても、表の番号と表題で取り出す表を指定できる
- pypdf を開発用の依存から本体の依存に移し、`google-genai` を足す
- テストでは LLM の応答をモックにし（Step1-A2 の decisions/0004 と同じ）、実 API を呼ぶテストには `integration` マーカーを付ける
- スキャンした PDF での精度はわからない。画像で渡す・抜き出した文字で渡すとの比較は、必要になったら別の ADR で足す
- 比べるときに値の書き方をどこまで揃えるか（「1,000.00」と「1000.00」など）は、比べる仕組みを作るときに別に決める
