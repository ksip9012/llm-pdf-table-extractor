# llm-pdf-table-extractor

総務省統計局「日本の統計 2026」の PDF から統計表を LLM で構造化データにし、同じ表の Excel を正解にして精度を測る（個人プロジェクト Step2）。

## セットアップ

[mise](https://mise.jdx.dev/) で Python と uv の版をそろえ、uv で依存を入れる（版は `mise.toml` と `uv.lock` で固定）。

```bash
mise trust
mise install
uv sync
uv run pre-commit install   # コミットの前に mise run check を動かす
mise run fetch              # 元データを落とし、sha256 を確かめる
```

## テストの実行方法

```bash
mise run check   # ruff check・ruff format --check・pyright・pytest（CI と同じ）
mise run fix     # ruff の自動修正と format
```

## 元データと出典

- 出典: 総務省統計局「日本の統計 2026」（https://www.stat.go.jp/data/nihon/）
- 利用規約: [公共データ利用規約 第1.0版（PDL1.0）](https://www.stat.go.jp/info/riyou.html)
- 置き場所（[decisions/0001](./decisions/0001-source-data-placement.md)）
  - 表ごとの xlsx: `data/xlsx/2026/`（リポジトリに入れている。統計局のファイルをそのまま置いたもので、加工していない）
  - 本全体の PDF: `mise run fetch` で `data/raw/` に落とす（リポジトリには入れない）
  - 一覧（URL と sha256）: `data/sources.toml`
- このリポジトリで作る構造化データ（整然データ）は、上の元データを加工して作成したもの

## 正解データ

PDF の表から取り出したデータの精度を測るための正解。どの表でも同じ縦長の形（1行 = 1セル）で持つ（[decisions/0002](./decisions/0002-truth-as-long-cells.md)）。

- `data/truth/<表の番号>.csv`: `table_id`・`row_label`・`column_label`・`value`・`unit`・`notes`
- `data/truth/<表の番号>.meta.json`: 表題・PDF のページ・基準日・注記の中身・資料
- `mise run truth` で xlsx から作り直す。正解の値・単位が PDF のページに書かれているかは、テストで確かめる（PDF がある手元だけ）

| 表 | 内容 | PDF のページ |
|---|---|---|
| 1-1 | 都道府県別面積（令和7年） | 30 |

## LLM で取り出して比べる

表のページだけを 1ページの PDF にして Gemini（Vertex AI）に読ませ、正解と同じ形で出させて比べる（[decisions/0003](./decisions/0003-gemini-with-single-page-pdf.md)・[0004](./decisions/0004-compare-cells.md)）。

```bash
gcloud auth application-default login
# GCP のプロジェクトを手元の mise.local.toml に書く（git の対象外）
#   [env]
#   GOOGLE_CLOUD_PROJECT = "<プロジェクト ID>"
mise run extract   # data/output/<表の番号>.csv に書く（実 API・有料）
mise run evaluate  # 正解と比べ、値の一致率と食い違いの一覧を出す
```

LLM の出力（`data/output/`）もリポジトリに入れる。notes の数字の裏付けにし、取り出し直したときは `git diff` で前回と変わったセルを見る。上書きしたら、notes も書き足す。

結果: [表 1-1 の最初の結果](./notes/table-1-1-first-run.md)（値の一致率 100%、96 セル）

## 技術選定理由

- [0001](./decisions/0001-source-data-placement.md): 表ごとの xlsx はリポジトリに入れ、本全体の PDF は落として使う
- [0002](./decisions/0002-truth-as-long-cells.md): 正解は、どの表でも同じ縦長の形（1行 = 1セル）で持つ
- [0003](./decisions/0003-gemini-with-single-page-pdf.md): LLM は Vertex AI の gemini-3.8-flash にし、表のページだけを 1ページの PDF で渡す
- [0004](./decisions/0004-compare-cells.md): 出力と正解は、見出しの組でセルを対応させ、値・単位・注記を分けて比べる
