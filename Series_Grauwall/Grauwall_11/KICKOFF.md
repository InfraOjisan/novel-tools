# KICKOFF — 第11回『南の川港』を動かす手順（人が端末で行う）

モデルへの「プロンプト」は、novelctl がパケットとして組み立てます（BRIEF の共通執筆ルールと各章の機能・CANON の本体とその章のカード・設定資料の抜粋・台帳・前章の結び・プロンプト）。`notes/` はパケットに入りません。

## 1. 準備（一度だけ）

リポジトリ直下の `.env` に、OpenRouter のキー（`OPENROUTER_API_KEY`）があること（値はここに書かない）。書き手と審査役のモデルは `config.json` で固定（書き手・磨き＝`anthropic/claude-haiku-5.5`、審査＝`openai/gpt-6-luna-pro`）。

## 2. 実行

```
cd Series_Grauwall/Grauwall_11
python3 tools/guard.py seal                  # 保護ファイルの指紋を記録（人が一度）
python3 tools/call_llm.py --ping writer
python3 tools/call_llm.py --ping reviewer
python3 tools/novelctl.py init
python3 tools/novelctl.py approve-canon      # canon/CANON.md を読んでから。start より先に
python3 tools/novelctl.py start              # 第1章から Haiku 5.5 が書く
python3 tools/novelctl.py status             # 進み具合
```

**試運転**：`status` で第3章が done になったら `touch STOP`。Claude が第1〜3章を読み、続けるかどうかを決めます。

止まったら `AGENTS.md` 第2節の表に従います。人が何かしたら `notes/INTERVENTIONS.md` に一行。
最後に Claude が全章を校正します。
