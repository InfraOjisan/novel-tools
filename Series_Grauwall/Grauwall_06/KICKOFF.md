# KICKOFF — 第6回『白塔の使者』を動かす手順（人が端末で行う）

モデルへの「プロンプト」は、novelctl がパケットとして組み立てます（BRIEF・設定資料の抜粋・台帳の抜粋・既に書かれた第1〜3章・プロンプト）。

## 1. 準備（一度だけ）

リポジトリ直下の `.env` に、次があること（値はここに書かない）。
```
NOVEL_PROVIDER=openrouter
NOVEL_PROVIDER_APIKEY=...
NOVEL_MODEL=aion-labs/aion-3.5-mini
```
- `NOVEL_MODEL` は**書き手と磨きにだけ**効きます（`config.json` の `llm.model_env_roles`）。審査役のモデルは `config.json` の `llm.profiles.reviewer.model`（Claude Haiku 5.5）と `fallback_models`（GPT-6 Luna Pro）で決まり、`.env` では変わりません。

## 2. 実行

```
cd Series_Grauwall/Grauwall_06
python3 tools/call_llm.py --ping writer
python3 tools/call_llm.py --ping reviewer
python3 tools/novelctl.py init
python3 tools/novelctl.py start              # 設計 → CANON審査 → CANONロックまで進んで止まる
#   canon/CANON.md を読む（第4節＝人物の行動原理、第13節＝差し込み申告）
python3 tools/novelctl.py approve-canon      # 人が端末で
python3 tools/novelctl.py start              # 第1〜3章は記録だけ、第4〜20章を Aion が書く。結合、最終審査まで
python3 tools/guard.py check
```

止まったら `AGENTS.md` 第2節の表に従います。人が何かしたら `notes/INTERVENTIONS.md` に一行。
最後に Claude が全章を校正します（第3回と同じ）。

## 3. 進行役エージェントに任せるときの指示文

---

あなたは、このフォルダ（Grauwall_06）の進行役です。まず `AGENTS.md` を最後まで読んでください。作者は Aion、審査役は Claude Haiku 5.5 で、あなたはどちらでもありません。

やることは次の三つだけです。
1. `python3 tools/novelctl.py start` で進め、`python3 tools/novelctl.py status` で様子を見る。章が四つ増えるごとに `python3 tools/guard.py check` を実行する。
2. `canon_hold` になったら止まり、`notes/REPORT.md` に CANON の要旨と第4節（人物の行動原理）と第13節（差し込み申告）を写して、人に知らせる。`approve-canon` はあなたには実行できません。人を待ってください。
3. `ESCALATE` が出たら止まり、コードと内容を `notes/REPORT.md` に書いて、人に知らせる。

してはいけないこと：このフォルダの外を読む・書く（`.env` を開く・表示するのも含む）。モデルの出力（`canon/`・`chapters/`・`state/`・`work/`）を書き換える。受け箱に答えを置く。保護ファイルを書き換える。`resolve --retry`・`resolve --relock`・`reset-chapter` を人の指示なしに実行する。ウェブ検索、パッケージの導入、git、外部への送信。

`STOP` ファイルが作業フォルダの直下にあれば、何もしないで人を待ってください。迷ったら、進まずに訊いてください。

---
