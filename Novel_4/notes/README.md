# Novel_4 — 星型チームの実戦（『夜明け前の運河便』）

- 司令塔（Claude）が `python3 tools/team.py` を1コマンドずつ回す。ワーカーは道具もメモリも持たない1回きりのAPI呼び出し。
- 接続先は `.env.local`（Git管理外）。Go：執筆役3＋編集・検査・台帳・審査。Aion だけ OpenRouter（`../.env`）。
- 手順：`canon` → 人が読む → `approve-canon --sha` → `write N --mode team|aion` → `judge N` → `proofread N` → Mac側の校正 → `proofread-apply N`。
- Aion の実行は1回の呼び出しが長い（推論が長い）。Mac のターミナルで `TEAM_NO_BUDGET=1 python3 tools/team.py write 1 --mode aion`。
- `STOP` を直下に置くと全員止まる（置くのは人。外すときは `mv STOP work/old/`）。
- 観測：`runs/<mode>/work/chNN/`（稿・編集の採否・検査の指摘と照合結果・台帳）、`runs/<mode>/logs/run.jsonl`。
