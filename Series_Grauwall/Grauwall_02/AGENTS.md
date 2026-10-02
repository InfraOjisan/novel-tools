# AGENTS.md — 進行役マニュアル（グラウヴァル・シリーズ第2回『新しい組合長』／系統A／作者＝Claude）

このディレクトリで動くエージェント（Claude / HermesAgent / OpenCode など）向けの指示です。
本文・設計・審査・記録は Claude（Opus 5.5）が受け箱方式で書きます。系統Aは謎解きではないので、公正判定（`fairness.py`）の工程は置きません。

| 工程 | 担当 | 仕組み |
|---|---|---|
| BRIEF（構造） | Claude＋プロデューサー | `BRIEF.md`（上位は `../SERIES_BIBLE.md`・`../SERIES_LEDGER.md`・`../EPISODE_PLAN.md`） |
| CANON（設定書）設計・審査 | Claude | `novelctl step` → パケット → `work/inbox/` に答え |
| CANON の確認 | プロデューサー | `pause_after_canon=true`。ロック後に止まる → `approve-canon` |
| 第1章の確認 | プロデューサー | 「小説として自然か」（企画表の手順4） |
| 各章 執筆・審査・LEDGER | Claude | 受け箱（`writer_cmd` / `reviewer_cmd` = `tools/inbox_llm.py`） |
| 校正 | Claude | `chapters/` を読み `output/final_proofread.md` を作る |
| 出版 | 人 | `novelctl epub --proofread`、なろうは `../../publish/narou/` |
| 記録 | Claude | 完成後、`../SERIES_LEDGER.md` に第2回の節を追記 |

---

## 0. 最重要ルール

1. **状態はディスクにしかない。** 迷ったら `python3 tools/novelctl.py status` → `NEXT:` に従う。
2. **進行は `novelctl.py` だけで行う。** パケットの組み立て、検査、LEDGER 更新、状態保存はすべてこのコマンドが行う。
3. **作者が Claude のとき**：`step` が `AWAITING_AUTHOR` で止まったら、`work/inbox/WAITING.txt` に書かれたパケットを読み、答えを `work/inbox/<パケット名から .packet.md を除いた名前>.md` に置いて `resolve` → `step`。
4. **ファイルを手で編集しない。** `canon/`・`chapters/`・`state/` はコマンド経由でのみ変わる。
5. **秘密を漏らさない。** CANON 第11節（作者だけが知ること）は本文に書かない。系統Bの書き手（Aion など）にこのディレクトリの `canon/` を渡さない。

## 1. メインループ（作者＝Claude）

```
status → packet design → work/inbox/design.md → step
      → packet canon-review → work/inbox/canon-review.md（JSON）→ step（ロック → 人の確認待ち）
      → 人が canon/CANON.md を確認 → approve-canon
第N章: packet write N → work/inbox/write_chNN.md → step
       packet review N → work/inbox/review_chNN.md（JSON）→ step
       packet ledger N → work/inbox/ledger_chNN.md → step
最終:  step（結合）→ packet final → work/inbox/final.md（JSON）→ step → DONE
```

## 2. エスカレーション対応表

| コード | 意味 | 対応 |
|---|---|---|
| `AWAITING_AUTHOR` | 受け箱に答えがない | パケットを読んで答えを置き、`resolve` → `step` |
| `CHAPTER_EXHAUSTED` | 章が規定稿数で合格しない | `work/chNN_feedback.md` を人に報告 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が `state/LEDGER.md` に追記 → `resolve --ledger-done` |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 意図した変更なら `resolve --relock` |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人に見せる |

## 3. 調整のつまみ（config.json）

| キー | 値 | 目安 |
|---|---|---|
| `chapter_chars` | 2,500〜5,000（目標3,000） | 一章＝なろうの一話。5,000字を超える章は書かない |
| `total_chars` | 32,000〜50,000 | 全体（目標36,000） |
| `ledger_fields` | STATE_MASTER / STATE_ERIKA / STATE_MAGDA / THREAD など | LEDGER の必須行 |
| `slot_plan` | BRIEF 4-2 と同じ | **BRIEF.md と必ず同時に変更する** |
| `pause_after_canon` | true | CANON ロック後にプロデューサー確認 |
