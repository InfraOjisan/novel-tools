# AGENTS.md — 進行役マニュアル（第三作「城塞都市の叙述ミステリ」／作者＝Claude・公正判定＝HermesAgent）

このディレクトリで動くエージェント（Claude / HermesAgent / OpenCode など）向けの指示です。
第三作は **Aion を使いません**。本文は Claude（Opus 5.5）が書き、HermesAgent は完成後に「ミステリとして読者に公正か」を判定します。
叙述トリックは地の文の一語（呼び名・代名詞・鐘の数）で成立したり壊れたりするため、文体の仕上げ工程は置きません。

| 工程 | 担当 | 仕組み |
|---|---|---|
| BRIEF（構造） | Claude | 人と相談して `BRIEF.md` を書く |
| CANON（設定書＋真相台帳）設計・審査 | Claude | `novelctl step` → パケット → `work/inbox/` に答え |
| 各章 執筆・審査・LEDGER | Claude | 同上（`writer_cmd` / `reviewer_cmd` = `tools/inbox_llm.py`） |
| 公正判定（読者役の推理＋公正監査） | **HermesAgent** | `tools/fairness.py`（第4節） |
| 校正 | Claude | `chapters/` を読み `output/final_proofread.md` を作る |
| 出版 | 人 | `novelctl epub --proofread` |

---

## 0. 最重要ルール

1. **状態はディスクにしかない。** 迷ったら `python3 tools/novelctl.py status` → `NEXT:` に従う。
2. **進行は `novelctl.py` だけで行う。** パケットの組み立て、検査、LEDGER 更新、状態保存はすべてこのコマンドが行う。
3. **作者が Claude のとき**：`step` が `AWAITING_AUTHOR` で止まったら、`work/inbox/WAITING.txt` に書かれたパケットを読み、答えを `work/inbox/<パケット名から .packet.md を除いた名前>.md` に置いて `resolve` → `step`。先に `python3 tools/novelctl.py packet <kind> [N]` でパケットを作って読み、答えを置いてから `step` してもよい。
4. **ファイルを手で編集しない。** `canon/`・`chapters/`・`state/` はコマンド経由でのみ変わる。
5. **真相を漏らさない。** HermesAgent が読者役（solve）をするときは、`canon/`・`state/`・`work/`（パケット以外）・`output/` を開かない。

## 1. ファイル構成

```
./
├── AGENTS.md / BRIEF.md / config.json
├── templates/            CANON（設定書＋真相台帳）・LEDGER の雛形（ミステリ版）
├── prompts/              各工程の依頼文（fair_solve.md / fair_audit.md が公正判定用）
├── tools/
│   ├── novelctl.py       進行エンジン
│   ├── inbox_llm.py      作者（Claude・人）の受け箱アダプタ
│   ├── fairness.py       公正判定（読者役の推理＋公正監査）
│   ├── call_llm.py       OpenRouter 呼び出し（fairness --api のときだけ使う）
│   └── make_epub.py      縦書き EPUB
├── canon/CANON.md        設定書＋真相台帳（ロック）。第11節が解答キー
├── state/                progress.json / LEDGER.md（CLUE 行・LIE 行つき）
├── chapters/chNN.md      確定稿
├── work/fair/            公正判定のパケットと答え
└── output/               final.md / final_report.md / fairness_report.md / *.epub
```

## 2. メインループ（作者＝Claude）

```
status → packet design → work/inbox/design.md → step
      → packet canon-review → work/inbox/canon-review.md（JSON）→ step（ロック）
第N章: packet write N → work/inbox/write_chNN.md → step
       packet review N → work/inbox/review_chNN.md（JSON）→ step
       packet ledger N → work/inbox/ledger_chNN.md → step
最終:  step（結合）→ packet final → work/inbox/final.md（JSON）→ step → DONE
判定:  python3 tools/fairness.py packets → HermesAgent が判定 → python3 tools/fairness.py report
```

## 3. エスカレーション対応表

| コード | 意味 | 対応 |
|---|---|---|
| `AWAITING_AUTHOR` | 受け箱に答えがない | パケットを読んで答えを置き、`resolve` → `step` |
| `CHAPTER_EXHAUSTED` | 章が規定稿数で合格しない | `work/chNN_feedback.md` を人に報告 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が `state/LEDGER.md` に追記 → `resolve --ledger-done` |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 意図した変更なら `resolve --relock` |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人に見せる |

## 4. HermesAgent による公正判定（完成後）

目的：この作品が「ミステリとして読者に公正か」を、作者（Claude）とは別の読み手が判定する。

1. `python3 tools/fairness.py packets`（`work/fair/` に solve ×5 と audit ×1 のパケットができる）
2. **読者役（solve）**：`work/fair/fair_solve_ch01.packet.md` 〜 `ch05` を、**一つずつ、毎回新しい会話（またはサブエージェント）で**読み、依頼どおりのJSONを `work/fair/fair_solve_chNN.answer.json` に保存する。
   - 読者役の間は、パケット以外のファイルを一切開かない（真相を知った読者は判定にならない）。
   - 第1章から順に。前の章の自分の答えも見ない。
3. **審判（audit）**：solve がすべて終わってから `work/fair/fair_audit.packet.md` を読み、JSONを `work/fair/fair_audit.answer.json` に保存する。
4. `python3 tools/fairness.py report` → `output/fairness_report.md` を人に報告する。
5. 別のモデルでも比べたいときは `config.json` の `llm.profiles.judge.model` を変えて `python3 tools/fairness.py run --api`（`.env` に OpenRouter のキーが必要）。

判定の見方：
- 第5章時点で「盗んだ者」「仕組んだ者」が当たっていれば、解ける（公正）。
- 第1〜2章で自信70以上で当たっていれば、手がかりが強すぎる（早すぎる看破）。
- 監査の high 指摘（語りの嘘・作法違反の嘘・解決編で初出の証拠）は、該当章を `reset-chapter N` して書き直す。

## 5. 調整のつまみ（config.json）

| キー | 値 | 目安 |
|---|---|---|
| `chapter_chars` | 6,000〜10,500（目標8,000） | 一章の字数 |
| `total_chars` | 30,000〜99,999 | 全体 |
| `ledger_fields` | CLUE / LIE / STATE_MASTER / STATE_BUNNY / SURFACE など | LEDGER の必須行 |
| `fairness.solve_chapters` | [1,2,3,4,5] | 読者役に推理させる章 |
| `llm.profiles.judge` | 判定に使うモデル（--api のときだけ） | |
