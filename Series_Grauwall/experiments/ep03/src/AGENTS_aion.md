# AGENTS.md — 進行役の手引き（グラウヴァル・シリーズ第3回『北街道の白い耳』／系統B／作者＝Aion 3.5 mini）

このフォルダでは、**Aion 3.5 mini が作者・審査・記録をすべて行います。** 進行役（人、または omp / agy / HermesAgent の一体）は、`tools/novelctl.py` を動かして、止まったら人に知らせるだけです。
Aion は OpenRouter 経由で `tools/call_llm.py` から呼ばれます。Aion が読むのはパケットだけで、パケットには BRIEF・設定資料の抜粋・台帳の抜粋・プロンプトが入ります。この AGENTS.md は Aion には渡りません（進行役のための手引きです）。

この回は、混成チーム（`../Grauwall_03_team/`）との比べ合いです。**Aion の書いたものに、進行役が手を入れないこと**が、比べ合いの前提です。

---

## 0. 最上位の約束（進行役が人でもエージェントでも同じ）

1. **この作業フォルダの外に出ない。** 例外は、リポジトリ直下の `.env` を `tools/call_llm.py` が読むことだけ（進行役は `.env` を開かない・表示しない・写さない）。
2. **Aion の出力を手で直さない。** `canon/`・`chapters/`・`state/`・`work/` のファイルを書き換えない。受け箱（`work/inbox/`）に答えを置かない（それをするとチームと同じ条件ではなくなる）。
3. **書き換えてはいけないもの。** `AGENTS.md`・`BRIEF.md`・`KICKOFF.md`・`config.json`・`tools/`・`prompts/`・`templates/`・`series/`・`guard/`。指紋で見張られていて、変わると novelctl が止まります。
4. **人の承認は人がする。** `approve-canon` は人が端末で行う（エージェントからは実行できないようにしてある）。`resolve --relock`・`reset-chapter`・`tools/guard.py seal`（指紋の張り直し）も人の判断で。
5. **STOP ファイルを見たら止まる。** 作業フォルダの直下に `STOP` があれば、novelctl は進まない。
6. **介入は記録する。** 人や進行役が何かした（`resolve --retry`、`reset-chapter`、設定の変更など）ら、`notes/INTERVENTIONS.md` に一行ずつ書く（日時・何をした・なぜ）。介入の数と中身は評価に含めます。

---

## 1. 動かし方

```
python3 tools/call_llm.py --ping writer      # 疎通とキーの確認（数十トークンだけ使う）
python3 tools/novelctl.py status             # 現在地
python3 tools/novelctl.py start              # 完了かエスカレーションまで、裏で step を繰り返す（すぐ戻る）
python3 tools/novelctl.py status             # 進み具合（ときどき見る）
python3 tools/guard.py check                 # 見張り番の点検（章が増えるたびに見る）
```

- 設計（design → canon-review）が通ると、CANON がロックされて `canon_hold` で止まります。**人が `canon/CANON.md` を読み、端末で `approve-canon` を実行**してから、もう一度 `start`。
- 一回の `start` で進むステップ数の上限は `run` の既定（200）です。章ごとの書き直しは最大3稿、設計は最大3回で、超えたら `ESCALATE` で止まります。これがループの歯止めです。

## 2. 止まったとき

| コード | 意味 | 対応 |
|---|---|---|
| `CHAPTER_EXHAUSTED` | 章が3稿で合格しない | `work/chNN_feedback.md` を人が読む。続けるなら人が `resolve --retry`（一章につき一回まで）して `INTERVENTIONS.md` に記録 |
| `LEDGER_FAILED` | 章の記録が書式を満たさない | 人が判断。手で記録を足すなら `INTERVENTIONS.md` に記録 |
| `CANON_MODIFIED` | ロック後に CANON が変わった | 誰が変えたかを確かめる。意図しない変更なら元に戻す |
| `GUARD_STOP` | STOP があるか、保護ファイルが変わった | 人が原因を確かめる |
| `FINAL_REVIEW_FAILED` | 最終審査で重大指摘 | `output/final_report.md` を人が読む |
| API のエラーが続く | OpenRouter 側の不調、キー、モデル名 | `--ping` で確かめる。直らなければ人に報告 |

## 3. 規則の中身

Aion が守る規則は `BRIEF.md`（とくに第0節「作者の裁量と、その責任」、2-9「シリーズの規律」、2-11「越えてはならない線」）にあります。混成チームと同じ BRIEF です。
差し込みの申告（CANON 第13節、ledger の INSERT 行）も同じ仕組みです。

## 4. 人への報告（進行役が notes/REPORT.md に書く）

- CANON がロックされたとき：作品の要旨、語りの形、差し込みの一覧（CANON 第13節）。
- 止まったとき：コードと、何を待っているか。
- 完成したとき：final の講評、持ち越しの差し込み、介入の数、使ったトークン（`logs/` から分かる範囲で）。
