# 第3回の実験：混成チーム 対 Aion 3.5 mini（『北街道の白い耳』）

同じ BRIEF・同じ設定資料の抜粋・同じプロンプト・同じ見張り番で、二つの書き手に第3回を書かせて比べます。
見たいのは文章の上手さだけではありません。**決められたことを守り、決められていない所で思い切ってやり、足したものの始末を自分でつけるか**です。

## 置いてあるもの

| ファイル | 誰が読む | 中身 |
|---|---|---|
| `README.md` | 人 | この説明 |
| `GOVERNANCE.md` | 人・ハーネスの運用者 | 上位統制ルール（環境・検査・約束の三層）と、始める前の確認表 |
| `EVAL.md` | プロデューサー | 採点表（失格／規則25／余白35／後始末20／小説20）と運用の記録欄 |
| `setup_ep03.py` | 人 | 二つの作業フォルダを、同じ材料から作る道具 |
| `src/` | （道具が使う） | BRIEF、AGENTS（チーム用・Aion用）、KICKOFF、プロンプト、テンプレート、道具、config の元 |
| `corpus/`（任意） | 道具 | 引き写しを見張りたい参考文を人が置く場所。置けば作業フォルダの `guard/corpus/` に入る |

作業フォルダ（`setup_ep03.py` が作る）：
- `Series_Grauwall/Grauwall_03_team/` … HermesAgent の混成チーム用。作者は受け箱方式（チームがパケットに答える）
- `Series_Grauwall/Grauwall_03_aion/` … Aion 用。作者は `call_llm.py` が OpenRouter の Aion を直接呼ぶ

二つの違いは `AGENTS.md`・`KICKOFF.md` と、`config.json` の書き手の指定（`writer_cmd` / `reviewer_cmd`）だけです。

## 手順

1. `GOVERNANCE.md` の確認表を見る。
2. 作業フォルダを作る（済んでいれば不要）：`python3 Series_Grauwall/experiments/ep03/setup_ep03.py --pack`
   - 設定資料と台帳は【秘密】を除いた抜粋だけを置きます。抜粋は作るたびに漏れ検査をし、引っかかったら何も作らずに止まります。
   - `--pack` で、チーム用を `dist/Grauwall_03_team.tar.gz` にまとめます。これを HermesAgent の VM に展開します（リポジトリ全体は渡さない）。
3. 混成チーム：`Grauwall_03_team/KICKOFF.md` の【】を埋めて、グループチャットに貼る。
4. Aion：`Grauwall_03_aion/KICKOFF.md` の手順で、人が端末から動かす（進行役エージェントに任せる場合は、そこにある指示文を渡す）。
5. どちらも CANON がロックされたら止まります。人が `canon/CANON.md` を読み、端末で `approve-canon`（指紋の入力が要る）。
6. 完成したら `EVAL.md` で採点。二つの作業フォルダを丸ごとコミットして残す。採った方を、いつもの流れ（校正 → EPUB → Romancer → なろう）に乗せる。

## この実験で足した仕組み（作業フォルダの tools/ だけ。Grauwall_02 以前は変えていない）

- `tools/guard.py`（新規）：STOP、保護ファイルの指紋、作業フォルダの形、越えてはならない線の言葉、既刊と参考文からの引き写し。
- `tools/novelctl.py`：毎 step の最初に guard を見る（`GUARD_STOP`）。章と CANON の機械検査に guard を足した。設計と設計審査のパケットに `series_files`（抜粋）を差し込む。CANON 第13節（差し込み申告）が無いと設計が通らない。`approve-canon` は端末からの指紋入力が要る。
- `tools/call_llm.py`：`.env` をリポジトリ直下まで探す。キー名 `NOVEL_PROVIDER_APIKEY` とモデル名 `NOVEL_MODEL` を読む。

企画表の「仕組みの改良候補」の一つ目（設定資料の抜粋をパケットへ自動で差し込み、系統Bでは【秘密】を機械的に除く）は、この実験の `series_files` と `setup_ep03.py` の抜粋・漏れ検査で形になりました。うまくいけば、第4回以降の標準にできます。
