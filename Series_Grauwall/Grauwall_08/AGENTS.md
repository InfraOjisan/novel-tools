# AGENTS.md — 進行役の手引き（グラウヴァル・シリーズ第8回『灰色山脈の古砦』／系統B）

> 2026-10-24（プロデューサー決定）：**CANON（章カードまで）は Claude Opus 5.5 が書いた。書き手は Aion 3.5 Mini（本文専任）、審査（チェッカー）は GPT-6 Luna Pro。** 前半で審査に詰まるなら書き手を Claude Haiku 5.5 に替える（`config.json` の `llm.profiles.writer.model`）。

このフォルダでは、**第1〜24章をすべて Aion Mini が書きます。** 設計（design）段階は使いません（CANON は `canon/CANON.md` に置いてある）。
- **書き手（writer）**：`aion-labs/aion-3.5-mini`（予備 `anthropic/claude-haiku-5.5`）。各章の本文と磨き。
- **審査役（reviewer）**：`openai/gpt-6-luna-pro`（予備 Haiku 5.5）。各章の審査（CANON との整合・嘘の不在・矛盾・誤字）、章の記録（LEDGER）、最終審査。

進行役（人、または omp / agy / HermesAgent の一体）は、`tools/novelctl.py` を動かして、止まったら人に知らせるだけです。モデルが読むのはパケットだけで、この AGENTS.md と `notes/` はモデルには渡りません。

---

## 0. 最上位の約束（進行役が人でもエージェントでも同じ）

1. **この作業フォルダの外に出ない。** 例外は、リポジトリ直下の `.env` を `tools/call_llm.py` が読むことだけ（進行役は `.env` を開かない・表示しない・写さない）。
2. **モデルの出力を手で直さない。** `canon/`・`chapters/`（第4章以降）・`state/`・`work/` のファイルを書き換えない。受け箱（`work/inbox/`）に答えを置かない。
3. **書き換えてはいけないもの。** `AGENTS.md`・`BRIEF.md`・`KICKOFF.md`・`config.json`・`tools/`・`prompts/`・`templates/`・`series/`・`guard/`・`canon/CANON.md`（承認後）。`notes/AUTHOR_ONLY.md` は開かない（作者のメモ。モデルにも渡さない）。指紋で見張られていて、変わると novelctl が止まります。
4. **人の承認は人がする。** `approve-canon` は人が端末で行う。`resolve --relock`・`reset-chapter`・`tools/guard.py seal` も人の判断で。
5. **STOP ファイルを見たら止まる。**
6. **介入は記録する。** `notes/INTERVENTIONS.md` に一行ずつ（日時・何をした・なぜ）。

---

## 1. 動かし方

```
python3 tools/call_llm.py --ping writer      # 書き手（Aion Mini）の疎通
python3 tools/call_llm.py --ping reviewer    # 審査役（GPT-6 Luna Pro）の疎通
python3 tools/novelctl.py init               # 初回だけ
python3 tools/novelctl.py approve-canon      # 人が端末で（canon/CANON.md を読んでから）。**start より先に**
python3 tools/novelctl.py start              # 第1章から書く（バックグラウンド）
python3 tools/novelctl.py status
python3 tools/guard.py check
```

- **approve-canon より前に start しない。** design 段階が動いて canon/CANON.md を上書きしてしまう。
- **試運転：第3章が done になったら `STOP` ファイルを置いて止める**（`touch STOP`）。Claude が第1〜3章を読んで、続けるか書き手を替えるかを決める。再開は `STOP` を消して `start`。

## 2. 止まったとき

| コード | 意味 | 対応 |
|---|---|---|
| `CHAPTER_EXHAUSTED` | 章が3稿で合格しない | `work/chNN_feedback.md` を人が読む。続けるなら人が `resolve --retry` して記録 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が判断 |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 誰が変えたかを確かめる |
| `GUARD_STOP` | STOP があるか、保護ファイルが変わった | 人が原因を確かめる |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人が読む |
| API のエラーが続く | OpenRouter 側の不調、キー、モデル名 | `--ping writer` / `--ping reviewer` で確かめる |

## 3. 規則の中身

モデルが守る規則は `BRIEF.md`（とくに第0節・第0-1節、2-9「シリーズの規律」、2-11「越えてはならない線」）にあります。名前のある人物の行動原理は CANON 第4節にある。審査役がそれと、**この回は嘘を一つも置かない**ことを確かめる。

## 4. 人への報告（進行役が notes/REPORT.md に書く）

- CANON がロックされたとき：作品の要旨、人物の行動原理の一覧、差し込みの一覧（CANON 第13節）。
- 止まったとき：コードと、何を待っているか。
- 完成したとき：final の講評、持ち越しの差し込み、介入の数、使ったトークンと費用（`logs/` から分かる範囲で。書き手と審査役を分けて）。
