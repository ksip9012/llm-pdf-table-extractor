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

## 技術選定理由

- [0001](./decisions/0001-source-data-placement.md): 表ごとの xlsx はリポジトリに入れ、本全体の PDF は落として使う
