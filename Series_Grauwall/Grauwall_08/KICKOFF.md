# KICKOFF — 第8回『灰色山脈の古砦』を動かす手順（人が端末で行う）

モデルへの「プロンプト」は、novelctl がパケットとして組み立てます（BRIEF の共通執筆ルールと各章の機能・CANON の本体とその章のカード・設定資料の抜粋・台帳・前章の結び・プロンプト）。`notes/` はパケットに入りません。

## 1. 準備（一度だけ）

リポジトリ直下の `.env` に、次があること（値はここに書かない）。
```
NOVEL_PROVIDER=openrouter
NOVEL_PROVIDER_APIKEY=...
# NOVEL_MODEL は使わない（書き手は config.json で aion-3.5-mini に固定）
```

## 2. 実行

```
cd Series_Grauwall/Grauwall_08
python3 tools/guard.py seal                  # 保護ファイルの指紋を記録（人が一度）
python3 tools/call_llm.py --ping writer
python3 tools/call_llm.py --ping reviewer
python3 tools/novelctl.py init
python3 tools/novelctl.py approve-canon      # canon/CANON.md を読んでから。start より先に
python3 tools/novelctl.py start              # 第1章から Aion Mini が書く
python3 tools/novelctl.py status             # 進み具合
```

**試運転**：`status` で第3章が done になったら `touch STOP`。Claude が第1〜3章を読み、続けるか書き手を Haiku 5.5 に替えるかを決めます。替えるときは `config.json` の `llm.profiles.writer.model` と `polisher.model` を `anthropic/claude-haiku-5.5` にし、`python3 tools/guard.py seal` をやり直します。

止まったら `AGENTS.md` 第2節の表に従います。人が何かしたら `notes/INTERVENTIONS.md` に一行。
最後に Claude が全章を校正します。
