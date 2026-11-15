#!/usr/bin/env python3
"""bt01 の箱を作る（モデルに渡すのは箱だけ）

  python3 tools/make_box.py OUTDIR [NAME]

NAME を付けると、そのモデル一本だけの箱にする（ほかのモデルの答えを読めないように、一モデル一箱を推奨）。

OUTDIR に PROMPT.md・TEXT.md・results/・RUN.md を置く。正解表（gold/）と設定資料は入れない。
**OUTDIR はリポジトリの外にしてください。** ハーネスが親フォルダをたどると、設定資料の【秘密】が読めてしまう。
"""
import sys, os, shutil
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
G = yaml.safe_load(open(os.path.join(ROOT, "gold", "GOLD.yaml"), encoding="utf-8"))

RUNS = [   # opencode で動かす三つは、OpenCode Go のモデル
    ("agy", "Claude Sonnet 5.5", "agy-sonnet-5.5"),
    ("agy", "Gemini 3.8 Flash", "agy-gemini-3.8-flash"),
    ("Codex", "GPT-6.1-Sol（high）", "codex-gpt-6.1-sol-high"),
    ("opencode", "gpt-6-luna", "ocg-gpt-6-luna"),
    ("opencode", "claude-haiku-5-5", "ocg-claude-haiku-5-5"),
    ("opencode", "mimo-v2.6-flash", "ocg-mimo-v2.6-flash"),
]

# 箱に入ってはいけない語（本文には出ず、設定資料にだけある語）
LEAK = ["月の森", "聞き耳", "B′", "身代わりと交換", "候補A", "SERIES_BIBLE", "正解表", "GOLD"]

def main():
    out = os.path.abspath(sys.argv[1])
    only = sys.argv[2] if len(sys.argv) > 2 else None
    runs = [r for r in RUNS if r[2] == only] or ([("?", "?", only)] if only else RUNS)
    if out.startswith(REPO + os.sep):
        sys.exit("箱はリポジトリの外に作ってください（設定資料が読めてしまう）")
    os.makedirs(os.path.join(out, "results"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "prompts", "PROMPT.md"), os.path.join(out, "PROMPT.md"))
    shutil.copy(os.path.join(REPO, G["text"]), os.path.join(out, "TEXT.md"))
    lines = ["# 実行の手順（人が読む）", "",
             "各ハーネスを**このフォルダで**起動し、下の一文を貼ってください。`<NAME>` は表の名前に置き換えます。", "",
             "```", "PROMPT.md の依頼に従ってください。読んでよいのは PROMPT.md と TEXT.md だけです。答えの JSON を results/<NAME>.json に書いてください。", "```", "",
             "| ハーネス | モデル | NAME |", "|---|---|---|"]
    lines += [f"| {h} | {m} | `{n}` |" for h, m, n in runs]
    lines += ["", "全部そろったら、リポジトリ側で：", "",
              f"```\npython3 Series_Grauwall/experiments/bt01/tools/score.py {out}/results {out}/TEXT.md\n```", "",
              "- 一つのモデルにつき一回。余裕があれば二回目を `<NAME>-2` で。",
              "- 途中で本文以外（ウェブ、親フォルダ、ホームの検索）を見に行ったハーネスは、その回を無効にしてください。",
              "- 終わったら、ハーネスのログ（実行したコマンド・開いたファイル）を一緒に保存してください。"]
    open(os.path.join(out, "RUN.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    bad = []
    for f in ("PROMPT.md", "RUN.md"):
        t = open(os.path.join(out, f), encoding="utf-8").read()
        bad += [(f, w) for w in LEAK if w in t]
    t = open(os.path.join(out, "TEXT.md"), encoding="utf-8").read()
    bad += [("TEXT.md", w) for w in LEAK if w in t]
    if bad:
        sys.exit(f"漏れ：{bad}")
    print(f"箱：{out}（PROMPT.md / TEXT.md {len(t):,}字 / RUN.md / results/）漏れなし")

if __name__ == "__main__":
    main()
