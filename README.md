# novel-tools

Aion 3.5 Mini（OpenRouter 経由）を使って短編小説を自動生成・審査・出版まで進めるためのツールキットです。
進行役エージェント（claude code / OpenCode など）が AGENTS.md を読んで `novelctl.py` を回す想定で作られています。

## 構成

`Novel_N/` の実プロジェクトは基本的に `Novel_base/` のコピーです。

```
 Novel_base/        ← テンプレート・雛形（新規プロジェクトはここからコピー）
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

 Novel_1/ Novel_2/ Novel_3/ Series_Grauwall/
                    ← 実作品（作品ごとのパラメータ直しは config.json と BRIEF.md）

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
