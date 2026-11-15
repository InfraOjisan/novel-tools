#!/usr/bin/env python3
"""bt02 の箱を作る（一モデル一箱。リポジトリの外に）

  python3 tools/make_box.py PARENT_DIR TEXT.md NAME...

PARENT_DIR/bt02_<NAME>/ に PROMPT.md・TEXT.md・SIGNALS.md・RUN.md・results/ を置く。
SIGNALS.md は work/SIGNALS.md（tools/merge.py の出力）。下読みの記号 A〜F とモデル名の対応は箱に入れない。
"""
import sys, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
LEAK = ["月の森", "聞き耳", "B′", "身代わりと交換", "候補A", "SERIES_BIBLE", "正解表", "GOLD",
        "メルヒオル", "カルトブルン", "古砦", "エーリカ", "無縁墓地", "二一二年", "命令書", "川原の小石",
        "codex", "gemini", "sonnet", "haiku", "luna", "mimo", "GPT", "Claude"]

def main():
    parent, text, names = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]
    if parent.startswith(REPO + os.sep):
        sys.exit("箱はリポジトリの外に作ってください")
    sig = open(os.path.join(ROOT, "work", "SIGNALS.md"), encoding="utf-8").read()
    bad = [w for w in LEAK if w.lower() in sig.lower()]
    if bad: sys.exit(f"SIGNALS.md に漏れ：{bad}")
    for n in names:
        d = os.path.join(parent, f"bt02_{n}")
        os.makedirs(os.path.join(d, "results"), exist_ok=True)
        shutil.copy(os.path.join(ROOT, "prompts", "PROMPT.md"), os.path.join(d, "PROMPT.md"))
        shutil.copy(os.path.join(ROOT, "work", "SIGNALS.md"), os.path.join(d, "SIGNALS.md"))
        shutil.copy(text, os.path.join(d, "TEXT.md"))
        open(os.path.join(d, "RUN.md"), "w", encoding="utf-8").write(
            "# 実行の手順（人が読む）\n\nハーネスを**このフォルダで**起動し、下の一文を貼ってください。\n\n```\n"
            f"PROMPT.md の依頼に従ってください。読んでよいのは PROMPT.md・TEXT.md・SIGNALS.md だけです。答えの JSON を results/{n}.json に書いてください。\n```\n\n"
            "- このフォルダでは、このモデルだけを動かしてください（別のモデルを動かすと上書きされます）。\n"
            "- ハーネスのログ（実行したコマンド・開いたファイル）も残してください。\n")
        print("箱：", d)

if __name__ == "__main__":
    main()
