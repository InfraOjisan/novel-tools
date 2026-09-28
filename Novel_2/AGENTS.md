# AGENTS.md — 進行役マニュアル（第二作「姉妹の一年」／作者＝Claude・文体＝Aion）

このディレクトリで動くエージェント（Claude / Hermes Agent / OpenCode など）向けの指示です。
第一作（Novel_1）とは役割が逆です。**本文は Claude（Opus 5.5）が書き、Aion 3.5 Mini は文体の仕上げ（色つけ）だけを行います。**

| 工程 | 担当 | 仕組み |
|---|---|---|
| BRIEF（構造） | Claude | 人と相談して `BRIEF.md` を書く |
| CANON 設計・審査 | Claude | `novelctl step` → パケット → `work/inbox/` に答え |
| 各章 執筆・審査・LEDGER | Claude | 同上（`writer_cmd` / `reviewer_cmd` = `tools/inbox_llm.py`） |
| 文体の仕上げ | Aion 3.5 Mini | `novelctl start polish`（`polisher_cmd` = `tools/call_llm.py … polisher`） |
| 校正 | Claude | `polished/` を読み `output/final_proofread.md` を作る |
| 出版 | 人 | `novelctl epub --proofread` |

---

## 0. 最重要ルール

1. **状態はディスクにしかない。** 迷ったら `python3 tools/novelctl.py status` → `NEXT:` に従う。
2. **進行は `novelctl.py` だけで行う。** パケットの組み立て、検査、LEDGER 更新、状態保存はすべてこのコマンドが行う。
3. **作者が Claude のとき**：`step` が `AWAITING_AUTHOR` で止まったら、`work/inbox/WAITING.txt` に書かれたパケットを読み、答えを `work/inbox/<パケット名から .packet.md を除いた名前>.md` に置いて `resolve` → `step`。先に `python3 tools/novelctl.py packet <kind> [N]` でパケットを作って読み、答えを置いてから `step` してもよい（止まらずに進む）。
   - 答えの書式は各パケット末尾の「依頼」に従う（本文なら `# 第N章　章題` から、審査なら JSON だけ、LEDGER なら `## CHnn` から）。
   - 審査（review）は自分の原稿でも甘くしない。機械検査（字数・途中切れ・管理用語）は novelctl が別に行う。
4. **Aion（仕上げ）は台詞・出来事・最後の一文を変えてはいけない。** novelctl が字数比・台詞数・場面転換数・最後の一文を機械検査し、不合格なら修正指示つきでやり直させる。
5. **ファイルを手で編集しない。** `canon/`・`chapters/`・`state/`・`polished/` はコマンド経由でのみ変わる。
6. `step` / `run` / `polish` を制限時間のあるツールから直接長時間実行しない。Aion を呼ぶ工程は `python3 tools/novelctl.py start polish`（切り離し実行）→ `status` で見守る。

---

## 1. ファイル構成

```
./
├── AGENTS.md / BRIEF.md / config.json
├── templates/            CANON・LEDGER の雛形（姉妹版）
├── prompts/              各工程の依頼文（polish.md が Aion 用）
├── tools/
│   ├── novelctl.py       進行エンジン（polish 工程・AWAITING_AUTHOR を追加）
│   ├── inbox_llm.py      作者が API で呼べないとき（Claude・人）の受け箱アダプタ
│   ├── call_llm.py       OpenRouter 呼び出し（Aion）
│   ├── make_epub.py      縦書き EPUB
│   └── proofread_apply.py 校正の適用
├── canon/CANON.md        設定書（ロック）
├── state/                progress.json / LEDGER.md
├── chapters/chNN.md      Claude の確定稿
├── polished/chNN.md      Aion の仕上げ稿
├── work/                 パケット・答え（work/inbox/done/）・審査結果・仕上げの各稿
├── output/               final.md / polished.md / final_proofread.md / *.epub / 各レポート
└── images/               cover.jpg（表紙） / frontispiece.jpg（口絵）
```

## 2. セットアップ

1. Aion 工程のために、プロジェクト直下に `.env`（1行 `OPENROUTER_API_KEY=sk-or-...`）を人が置く。共有・コミットしない。
2. `python3 tools/call_llm.py --ping polisher` が `PING OK` を返すことを確認。
3. `python3 tools/novelctl.py init`

## 3. メインループ（作者＝Claude）

```
status → packet design → 答えを work/inbox/design.md に置く → step
      → packet canon-review → work/inbox/canon-review.md（JSON）→ step（ロック）
第N章: packet write N → work/inbox/write_chNN.md → step
       packet review N → work/inbox/review_chNN.md（JSON）→ step（合格なら chapters/ に確定）
       packet ledger N → work/inbox/ledger_chNN.md → step（LEDGER 追記、次章へ）
最終:  step（結合）→ packet final → work/inbox/final.md（JSON）→ step → DONE
仕上げ: start polish → status（全章 polished/ にそろうまで）
      → assemble --polished → 校正 → epub --proofread
```

## 4. エスカレーション対応表

| コード | 意味 | 対応 |
|---|---|---|
| `AWAITING_AUTHOR` | 受け箱に答えがない | パケットを読んで答えを置き、`resolve` → `step` |
| `CALL_FAILED` / `CALL_TIMEOUT` | Aion 呼び出しの失敗 | `work/*.out.stderr` の末尾を人に報告（401=キー、402=残高、404=モデル名、429=混雑） |
| `CHAPTER_EXHAUSTED` | 章が規定稿数で合格しない | `work/chNN_feedback.md` を人に報告 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が `state/LEDGER.md` に追記 → `resolve --ledger-done` |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 意図した変更なら `resolve --relock` |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人に見せる |

仕上げ（polish）が3回とも機械検査に落ちた章は、`polished/` に入らず `work/polish_chNN_a*.md` に残る。原稿のまま使うか、人が選ぶ。

## 5. 調整のつまみ（config.json）

| キー | 値 | 目安 |
|---|---|---|
| `chapter_chars` | 5,600〜9,000（目標7,000） | 1季節あたりの字数 |
| `ledger_fields` | STATE_ANE / STATE_IMOTO など | LEDGER の必須行（作品ごとに変える） |
| `polish.len_ratio_min/max` | 0.9 / 1.3 | 仕上げ後の字数比の許容範囲 |
| `polish.dialogue_ratio_min` | 0.85 | 台詞（「」）の数がこれ未満に減ったら不合格 |
| `llm.profiles.polisher` | temperature 0.75 / reasoning medium | 色が薄ければ temperature を上げる |
