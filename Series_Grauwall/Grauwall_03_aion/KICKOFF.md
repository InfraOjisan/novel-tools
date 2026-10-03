# KICKOFF — Aion 3.5 mini で書く手順（人が端末で行う。進行役エージェントに任せる場合は末尾の指示文を渡す）

Aion への「プロンプト」は、novelctl がパケットとして組み立てます（BRIEF・設定資料の抜粋・台帳の抜粋・プロンプト）。人が Aion に直接話しかけることはありません。混成チームと同じ BRIEF・同じプロンプト・同じ見張り番で動きます。

## 1. 準備（一度だけ）

リポジトリ直下の `.env` に、次の三つがあること（値はここに書かない）。
```
NOVEL_PROVIDER=openrouter
NOVEL_PROVIDER_APIKEY=...
NOVEL_MODEL=aion-labs/aion-3.5-mini
```
`tools/call_llm.py` は、作業フォルダ → 親 → その親（リポジトリ直下）の順に `.env` を探します。モデル名は `NOVEL_MODEL` があればそれを使います。

## 2. 実行

```
cd Series_Grauwall/Grauwall_03_aion
python3 tools/call_llm.py --ping writer      # 疎通の確認
python3 tools/novelctl.py status
python3 tools/novelctl.py start              # 設計 → 設計審査 → CANON ロックまで進んで止まる
python3 tools/novelctl.py status             # canon_hold になったら
#   canon/CANON.md を読む（差し込み申告＝第13節も）
python3 tools/novelctl.py approve-canon      # 人が端末で。指紋の入力を求められる
python3 tools/novelctl.py start              # 第1章〜第16章、結合、最終審査まで
python3 tools/guard.py check                 # 途中でも、最後にも
```

止まったら `AGENTS.md` 第2節の表に従います。人が何かしたら `notes/INTERVENTIONS.md` に一行。

## 3. 進行役エージェントに任せるときの指示文（omp / agy / HermesAgent 一体など）

---

あなたは、このフォルダ（Grauwall_03_aion）の進行役です。まず `AGENTS.md` を最後まで読んでください。作者は Aion で、あなたは作者ではありません。

やることは次の三つだけです。
1. `python3 tools/novelctl.py start` で進め、`python3 tools/novelctl.py status` で様子を見る。章が四つ増えるごとに `python3 tools/guard.py check` を実行する。
2. `canon_hold` になったら止まり、`notes/REPORT.md` に CANON の要旨と第13節（差し込み申告）を写して、人に知らせる。`approve-canon` はあなたには実行できません。人を待ってください。
3. `ESCALATE` が出たら止まり、コードと内容を `notes/REPORT.md` に書いて、人に知らせる。

してはいけないこと：このフォルダの外を読む・書く（`.env` を開く・表示するのも含む）。Aion の出力（`canon/`・`chapters/`・`state/`・`work/`）を書き換える。受け箱に答えを置く。保護ファイル（AGENTS.md・BRIEF.md・config.json・tools/・prompts/・templates/・series/・guard/）を書き換える。`resolve --retry`・`resolve --relock`・`reset-chapter` を人の指示なしに実行する。ウェブ検索、パッケージの導入、git、外部への送信。

`STOP` ファイルが作業フォルダの直下にあれば、何もしないで人を待ってください。迷ったら、進まずに訊いてください。

---
