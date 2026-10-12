# CHANGELOG

## v1.0.0（2026-10-12）

作品ごとに道具を複製して手で改造する運用から、**一つのエンジンと、それを使うアプリ**に移した。以後の変更は GitHub の issue で管理する（`design/v1.0/ISSUES.md`）。

### 追加
- `engine/`：Grauwall_06 の novelctl を汎用化した雛形（v1.0 エンジン）。
  - 汎用のプロンプト一式（設計・審査・執筆・書き直し・記録・最終審査・磨き）と、CANON テンプレートに「世界の前提（効く範囲つき）」の節。
  - 上位モデル（役 `premium`）による例外処理：`rescue canon`（CANON 全体を一度だけ直す）、`rescue chapter N`（指摘箇所だけ直す）、`proofread`（校正案を JSON に出す。原文が一か所に一致しない案は機械で却下）。
  - `redesign --feedback`（人の指示で CANON を再設計）、`status --json`、費用の家計簿 `logs/usage.jsonl`、`budget_usd`（予算の上限で止まる）。
  - `scaffold.py`：brief.json から BRIEF.md・config.json・CANON テンプレートを描き出し、lint する（手合わせの廃止）。
  - 回帰テスト `engine/tests/`（偽モデルで端から端まで。Python 3.9 以上）。
- `studio/`：テーマ → 提案（n 案・費用つき）→ 分類（収束／バリエーション／外れ値）→ BRIEF → 確定 → CANON → 執筆 → 校正 → EPUB の Web アプリ（標準ライブラリのみ）と、同じ工程の CLI。
- `studio/devtools/mock_openrouter.py`：費用をかけずに試す偽モデル。
- `harness/`：Claude Code 以外のハーネス（Hermes Agent / agy / omp）向けの AGENTS.md・開始プロンプト・道具の一覧・試験 L1〜L4 と採点。
- `design/v1.0/`：考察（ANALYSIS.md）と issue の草稿、`scripts/create_issues.py`。

### 変更
- `call_llm.py`：`NOVEL_LLM_BASE_URL` を近くの .env からも読む。1回ごとの費用を記録。
- `approve-canon`：studio のボタン（指紋の一致）でも承認できる。端末でない承認の試みはログに残る。承認すると止まり（escalation）も解く。
- `make_epub.py`・`extract_chapter`：二十を超える章番号の漢数字。
- `proofread_apply.py`：修正案を Python のリストから `output/proofread_edits.json` に。

### そのまま
- `Novel_base/` は旧い雛形として残す（新しい作品は `engine/` から。studio の「確定」か `scaffold.py create`）。
- `Novel_1`〜`Novel_5`、`Series_Grauwall/` の各回は、それぞれの道具のまま。
