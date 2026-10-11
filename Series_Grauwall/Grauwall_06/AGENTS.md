# AGENTS.md — 進行役の手引き（グラウヴァル・シリーズ第6回『白塔の使者』／系統B）

このフォルダでは、**第1〜3章は Claude が書いた本文（`chapters/ch01〜03.md`）を渡し、第4〜20章を Aion 3.5 mini が書きます。**
役割は二つに分かれています（`config.json` の `llm.profiles`）。
- **書き手（writer）**：Aion 3.5 mini。設計（CANON）と各章の本文。磨き（polisher）も Aion。
- **審査役（reviewer）**：Claude Haiku 5.5（OpenRouter `anthropic/claude-haiku-5.5`）。つながらないときは GPT-6 Luna Pro（`openai/gpt-6-luna-pro`）に自動で切り替わる。CANON の審査、各章の審査（CANONとの整合・矛盾・誤字）、章の記録（LEDGER）、最終審査を受け持つ。

進行役（人、または omp / agy / HermesAgent の一体）は、`tools/novelctl.py` を動かして、止まったら人に知らせるだけです。モデルが読むのはパケットだけで、この AGENTS.md はモデルには渡りません。

---

## 0. 最上位の約束（進行役が人でもエージェントでも同じ）

1. **この作業フォルダの外に出ない。** 例外は、リポジトリ直下の `.env` を `tools/call_llm.py` が読むことだけ（進行役は `.env` を開かない・表示しない・写さない）。
2. **モデルの出力を手で直さない。** `canon/`・`chapters/`（第4章以降）・`state/`・`work/` のファイルを書き換えない。受け箱（`work/inbox/`）に答えを置かない。
3. **書き換えてはいけないもの。** `AGENTS.md`・`BRIEF.md`・`KICKOFF.md`・`config.json`・`tools/`・`prompts/`・`templates/`・`series/`・`guard/`・`chapters/ch01〜03.md`。指紋で見張られていて、変わると novelctl が止まります。
4. **人の承認は人がする。** `approve-canon` は人が端末で行う。`resolve --relock`・`reset-chapter`・`tools/guard.py seal` も人の判断で。
5. **STOP ファイルを見たら止まる。**
6. **介入は記録する。** `notes/INTERVENTIONS.md` に一行ずつ（日時・何をした・なぜ）。

---

## 1. 動かし方

```
python3 tools/call_llm.py --ping writer      # Aion の疎通
python3 tools/call_llm.py --ping reviewer    # 審査役（Haiku 5.5、だめなら GPT-6 Luna Pro）の疎通
python3 tools/novelctl.py init               # 初回だけ
python3 tools/novelctl.py status
python3 tools/novelctl.py start              # 設計 → CANON審査 → CANONロックで止まる
#   canon/CANON.md を人が読む（第4節の行動原理、第13節の差し込み申告も）
python3 tools/novelctl.py approve-canon      # 人が端末で
python3 tools/novelctl.py start              # 第1〜3章は記録だけ取って通過し、第4章から Aion が書く
python3 tools/guard.py check
```

- 第1〜3章（`given_chapters`）は書き直されません。novelctl はその本文を審査役に読ませて記録（LEDGER）だけを作り、第4章へ進みます。
- 設計と CANON 審査のパケットには、第1〜3章の本文が「既に書かれた章」として入ります。

## 2. 止まったとき

| コード | 意味 | 対応 |
|---|---|---|
| `GIVEN_MISSING` | 渡された章（第1〜3章）のファイルがない | 人が `chapters/` を確かめる |
| `CHAPTER_EXHAUSTED` | 章が3稿で合格しない | `work/chNN_feedback.md` を人が読む。続けるなら人が `resolve --retry` して記録 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が判断 |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 誰が変えたかを確かめる |
| `GUARD_STOP` | STOP があるか、保護ファイルが変わった | 人が原因を確かめる |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人が読む |
| API のエラーが続く | OpenRouter 側の不調、キー、モデル名 | `--ping writer` / `--ping reviewer` で確かめる |

## 3. 規則の中身

モデルが守る規則は `BRIEF.md`（とくに第0節・第0-1節、2-9「シリーズの規律」、2-11「越えてはならない線」）にあります。名前のある人物には行動原理（欲しいもの／恐れているもの／理由）を書かせ、審査役がそれを確かめます（BRIEF 第0節の14）。

## 4. 人への報告（進行役が notes/REPORT.md に書く）

- CANON がロックされたとき：作品の要旨、人物の行動原理の一覧、差し込みの一覧（CANON 第13節）。
- 止まったとき：コードと、何を待っているか。
- 完成したとき：final の講評、持ち越しの差し込み、介入の数、使ったトークンと費用（`logs/` から分かる範囲で。書き手と審査役を分けて）。
