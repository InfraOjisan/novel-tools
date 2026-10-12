# novel-tools

生成 AI に小説を書かせるための道具一式です。v1.0（2026-10-12）から、**一つのエンジン（`engine/`）と、テーマから EPUB までを通すアプリ（`studio/`）**になりました。以後の変更は GitHub の issue で管理します（`design/v1.0/ISSUES.md`、`CHANGELOG.md`）。

## v1.0 の入口

| やりたいこと | 使うもの |
|---|---|
| 小説を一から書く（テーマ → 企画のコンペ → BRIEF → 執筆 → 校正 → EPUB） | `python3 studio/server.py` → http://127.0.0.1:8780（`studio/README.md`） |
| 同じことをスクリプトやエージェントから | `python3 studio/cli.py ...`（JSON 入出力） |
| 自分で書いた BRIEF から作品フォルダを作る | `python3 engine/tools/scaffold.py create brief.json works/<slug>` |
| Claude Code 以外のハーネスで動かす・どこまでできるか試す | `harness/`（AGENTS.md・KICKOFF.md・試験 L1〜L4） |
| 費用をかけずに試す | `python3 studio/devtools/mock_openrouter.py` |
| 回帰テスト | `python3 -m unittest discover -s engine/tests` |
| v1.0 の考え方 | `design/v1.0/ANALYSIS.md` |

```
 engine/            ← v1.0 の執筆エンジン（novelctl・scaffold・汎用のプロンプトとテンプレート・テスト）
 studio/            ← テーマから EPUB までのアプリと CLI
 harness/           ← 他のハーネス向けの手引きと試験
 works/<slug>/      ← studio で作った作品（studio.json と、確定後はエンジンの作業場所）
 design/v1.0/       ← 考察と issue の草稿
```

役ごとのモデル（既定）：書き手 Claude Haiku 5.5、審査役 GPT-6 Luna Pro、上位モデル（例外処理と校正だけ）Claude Opus 5.5。
書く・照合するのは安いモデルで何度でも、全体の整合を直すのは上位モデルで一回だけ、止めるかどうかは人。

---

## v1.0 より前の構成（各作品はそれぞれの道具のまま動きます）

Aion 3.5 Mini（OpenRouter 経由）を使って短編小説を自動生成・審査・出版まで進めるためのツールキットです。
進行役エージェント（claude code / OpenCode など）が AGENTS.md を読んで `novelctl.py` を回す想定で作られています。

## 構成

`Novel_N/` の実プロジェクトは基本的に `Novel_base/` のコピーです。

```
 Novel_base/        ← 旧い雛形（v1.0 からは engine/ を使う）
├── AGENTS.md       ← 進行役エージェント向けマニュアル
├── BRIEF.md        ← 執筆指示書（章立て・伏線配置・結末の方向性）
├── config.json     ← 字数・試行回数・モデル設定
├── templates/      ← CANON（設定書）と LEDGER（進行台帳）の雛形
├── prompts/        ← 各工程の依頼文
├── tools/
│   ├── novelctl.py ← 進行エンジン（状態管理・パケット組み立て・検査）
│   └── call_llm.py ← OpenRouter 呼び出し（標準ライブラリのみ）
├── canon/          ← 【生成物】設定書（第0フェーズ後にロック）
├── state/          ← 【生成物】progress.json（唯一の正）／LEDGER.md
├── chapters/       ← 【生成物】確定した各章
├── work/           ← 【生成物】パケット・生出力・審査結果・修正指示
├── output/         ← 【完成品】final.md ／ final_report.md ／ EPUB
├── blog/           ← 【生成物】ブログ用の派生物
└── logs/           ← 全ステップの記録

 Novel_1/ Novel_2/  ← 単発の実作品（作品ごとのパラメータ直しは config.json と BRIEF.md）

 Series_Grauwall/   ← グラウヴァル・シリーズ（設定資料・台帳・企画表は直下）
├── Grauwall_01/    ← 第1回『夜啼きの涙』（旧 Novel_3）
├── Grauwall_02/    ← 第2回『新しい組合長』（準備中）
└── Grauwall_NN/    ← 以後の回。Novel_base（足りない工程は直前の回）から複製

 Claude outputs/    ← チャット UI とのやりとりで作った中間物・画像など
```

出力物・ログ・作品ごとの成果物もすべて git に含めています。
「半分だけ育って止まった物語の断片」が失われると、後で人間が困るためです。

## セットアップ

1. OpenRouter の API キーを用意する。`call_llm.py` は次の順に探す：
   - 環境変数 `NOVEL_LLM_API_KEY` / `OPENROUTER_API_KEY` / `HERMES_CUSTOM_OPENROUTER_API_KEY`
   - プロジェクト直下の `.env`（1行 `OPENROUTER_API_KEY=sk-or-...`）。**リポジトリには含めないこと**
2. `python3 tools/call_llm.py --ping` が `PING OK` を返すことを確認（ごくわずかな費用）
3. `python3 tools/novelctl.py init`
4. `python3 tools/novelctl.py status` で `NEXT: ...` が出ることを確認

## 使い方（最短ループ）

```
python3 tools/novelctl.py start    # 切り離して実行。本体は最後まで走る
# 必要に応じて 2〜5 分おきに:
python3 tools/novelctl.py status
# DONE → 完成 / ESCALATE → AGENTS.md の対応表 / RUNNING → 待つ
```

進行役の詳細な手順・エスカレーション対応表は `Novel_base/AGENTS.md` を参照してください。

## 出版

校正・EPUB 化・読者評価リンクの付与については `Novel_base/AGENTS.md` の「9. 出版と読者評価」を参照。

```
python3 tools/novelctl.py epub                  # 縦書きEPUB を作る
python3 tools/novelctl.py epub --proofread      # 校正済みテキストから作る
```

## ライセンス

MIT License（LICENSE を参照）
