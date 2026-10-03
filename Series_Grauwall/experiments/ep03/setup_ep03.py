#!/usr/bin/env python3
"""setup_ep03 — 第3回『北街道の白い耳』の実験用に、二つの作業場所を同じ材料から作る。

  python3 Series_Grauwall/experiments/ep03/setup_ep03.py            両方を作る（既にあれば作らない）
  python3 Series_Grauwall/experiments/ep03/setup_ep03.py --only team
  python3 Series_Grauwall/experiments/ep03/setup_ep03.py --pack      混成チーム用を tar.gz にまとめる（VMへ渡す用）
  python3 Series_Grauwall/experiments/ep03/setup_ep03.py --no-latitude  BRIEF 第0節（裁量の条項）を外した版を Grauwall_03_<side>_nolat に作る（A/B比較用）
  python3 Series_Grauwall/experiments/ep03/setup_ep03.py --excerpt-only 抜粋だけ作って漏れ検査（作業場所は作らない）

作るもの:
  Series_Grauwall/Grauwall_03_team/   HermesAgent の混成チーム用（作者＝受け箱方式。チームがパケットに答える）
  Series_Grauwall/Grauwall_03_aion/   Aion mini 用（作者＝call_llm.py で OpenRouter の Aion を直接呼ぶ）

両方とも中身は同じ（BRIEF・設定資料の抜粋・プロンプト・道具・見張り番）。違うのは AGENTS.md・KICKOFF.md・config.json の書き手の指定だけ。
設定資料と台帳は【秘密】を除いた抜粋だけを置く（系統Bの規則）。抜粋は作るたびに漏れ検査をし、引っかかったら何も作らずに止まる。
"""
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
SERIES = HERE.parent.parent            # Series_Grauwall/
REPO = SERIES.parent
SIDES = ("team", "aion")

# 抜粋に出てはいけない言葉（出たら止まる）
LEAK = ["【秘密】", "第9節", "9-1", "9-5", "B′", "追手", "聞き耳", "冷たい赤い石", "すり替", "別人", "無縁墓地",
        "量る目", "靴を見て", "四十枚", "瓶の底", "底の一つ", "カフス", "白い布", "在りかを偽", "十三個目",
        "S1 ", "S1｜", "S2", "S3", "S4", "S10", "S11", "S12", "S13", "口に出さない", "最大の謎", "ルルとシグだと"]


# ---------------------------------------------------------------- 抜粋
def sections(text):
    """'## ' と '### ' の見出しで区切る。[(見出し行, 本文行のリスト)]"""
    out, head, buf = [], None, []
    for line in text.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            out.append((head, buf))
            head, buf = line, []
        else:
            buf.append(line)
    out.append((head, buf))
    return [(h, b) for h, b in out if h]


def strip_secret_marks(line):
    line = re.sub(r"\s*\*\*【秘密】[^*]*\*\*", "", line)
    line = re.sub(r"【秘密】（第9節）", "", line)
    return line


def bible_excerpt():
    src = (SERIES / "SERIES_BIBLE.md").read_text(encoding="utf-8")
    secs = sections(src)
    keep_prefix = ("## 1.", "## 2.", "### 2-", "## 3.", "### 3-", "## 4.", "### 4-", "## 5.", "### 5-",
                   "## 6.", "### 6-1", "### 6-3", "## 7.", "### 7-1", "### 7-2", "## 10.", "## 11.", "### 11-1", "## 12.")
    out = ["# グラウヴァル・シリーズ 設定資料（第3回・系統B向けの抜粋）",
           "",
           "> これは設定資料の抜粋です。ここに書かれた【正典】は守ってください。【余地】と、ここに書かれていないことは、BRIEF に従って作者が決めてよい所です。",
           "> 第3回の BRIEF が、この抜粋より細かく決めている所（出す人物・出さない人物など）は、BRIEF に従ってください。",
           ""]
    for head, body in secs:
        if not head.startswith(keep_prefix):
            continue
        lines = []
        for line in body:
            if "最大の謎" in line or "マスターの蓄え" in line:
                continue
            if head.startswith("## 7.") or head.startswith("### 7-"):
                # 人物：この回に出る者だけ。秘密につながる行は落とす
                if head.startswith("### 7-1") and line.startswith("- **ザザ**"):
                    continue
                if head.startswith("### 7-2") and line.startswith("- ") and not line.startswith("- **トマス**"):
                    continue
            if head.startswith("## 10."):
                if line.startswith("| S") and not line.startswith("| S6 "):
                    continue
                line = line.replace("（9-1の候補Bと両立させる）", "")
            if head.startswith("### 4-2") and "月の森" in line:
                line = "- 【余地】**月の森**：兎人族の故郷と噂される西の森。"
            if head.startswith("### 11-1"):
                line = line.replace("**第9節は渡さない。**", "").replace("第10節のうち使う糸（S6・S7など）。", "第10節のうち使う糸。")
            if head.startswith("## 12."):
                line = line.replace("ルル（故人）、シグ（故人）", "ルル、シグ（第1回の人物。この回には出さない）")
            lines.append(strip_secret_marks(line))
        if head.startswith("### 6-1"):
            head = "### 6-1. 間取り（錆び釘亭）"
        out.append(head)
        out += lines
        if head.startswith("### 7-2"):
            out += ["### 7-5. 北街道の亡骸（第1回の公の記録）",
                    "",
                    "- 第1回の翌朝、隊商が北街道の三つ目の一里塚の先の棘草の中で、**灰色の狼と白い耳の娘**の亡骸を見つけた。喉を細い刃で一突き。財布も荷もなかった。公には野盗の仕業とされた。",
                    "- 街の人間は、第1回で北門を出た灰狼族の若者と、錆び釘亭で給仕をしていた兎人の娘だと思い込んだ。**亡骸の身元は、誰も確かめていない。** 人間は亜人の個体を見分けない。それ以上、誰も確かめなかった。",
                    "- 【正典】以後の作品で、**亡骸を名前で特定する記述を書かない**。人間の登場人物は「灰色と白い耳の娘」「あのバニー」としか言わない。地の文も、その二人が死んだとも生きているとも書かない。",
                    ""]
    text = "\n".join(out).strip() + "\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


LEDGER_DROP = ["カフス", "白い布", "見たものを口に出さない", "あなたは昔から"]
LEDGER_REPLACE = {
    "SUMMARY: ロズモンド夫人の紅玉": "SUMMARY: ロズモンド夫人の紅玉「夜啼きの涙」の盗難事件。前組合長バルタザールが盗賊ニコに盗ませ、灰狼族に着せようとした。真相は錆び釘亭の酒場番が解き明かした。灰狼族の若者は掟でヴェイの身代わりに北門から追放され、錆び釘亭の給仕だった兎人の娘が彼を追って北門を出た。翌朝、北街道で灰色の狼と白い耳の娘の亡骸が見つかり、街は二人だと思い込んだ。紅玉は公には行方知れず。",
    "THREAD: S1〜S12": "THREAD: シリーズの長い糸はすべて未決着。",
    "THREAD: S5 進行": "THREAD: S5 進行（内示は退けられ、助成の打ち切りは春の議へ）。S8 継続（裏口のスープは店の決まり）。",
}


def ledger_excerpt():
    src = (SERIES / "SERIES_LEDGER.md").read_text(encoding="utf-8")
    out = ["# グラウヴァル・シリーズ 台帳（第3回・系統B向けの抜粋）", "",
           "> 第1回・第2回で本文に確定した事実と、人物の状態です。ここに書かれた FACT・STATE に矛盾しないこと。", ""]
    started = False
    for line in src.splitlines():
        if line.startswith("## 第"):
            started = True
        if not started:
            continue
        if line.startswith("SECRET:") or any(w in line for w in LEDGER_DROP):
            continue
        for k, v in LEDGER_REPLACE.items():
            if line.startswith(k):
                line = v
        line = line.replace("街はルルとシグだと思い込んだが", "街は第1回で北門を出た二人だと思い込んだが")
        out.append(line)
    return "\n".join(out).strip() + "\n"


def leak_check(name, text):
    hits = [w for w in LEAK if w in text]
    if hits:
        sys.exit(f"STOP: {name} に秘密につながる語があります：{hits}。setup_ep03.py の抜粋の規則を直してください。何も作っていません。")


# ---------------------------------------------------------------- 設定
def config(side):
    base = json.loads((SRC / "config_base.json").read_text(encoding="utf-8"))
    over = base.pop("sides")[side]
    base["publish"]["credits"] = over.pop("publish_credits")
    base["publish"]["ai_disclosure"] = over.pop("publish_ai_disclosure")
    base.update(over)
    return base


def build(side, bible, ledger, latitude, suffix=""):
    dest = SERIES / f"Grauwall_03_{side}{suffix}"
    if dest.exists():
        print(f"SKIP: {dest.relative_to(REPO)} は既にあります（作り直すなら、人が中身を確かめてから消してください）。")
        return dest
    dest.mkdir()
    for d in ["tools", "prompts", "templates"]:
        shutil.copytree(SRC / d, dest / d, ignore=shutil.ignore_patterns("__pycache__"))
    brief = (SRC / "BRIEF.md").read_text(encoding="utf-8")
    if not latitude:
        brief = re.sub(r"## 0\. 作者の裁量と、その責任.*?\n---\n", "", brief, flags=re.S)
    (dest / "BRIEF.md").write_text(brief, encoding="utf-8")
    shutil.copy(SRC / f"AGENTS_{side}.md", dest / "AGENTS.md")
    shutil.copy(SRC / f"KICKOFF_{side}.md", dest / "KICKOFF.md")
    (dest / "series").mkdir()
    (dest / "series" / "SERIES_BIBLE.md").write_text(bible, encoding="utf-8")
    (dest / "series" / "SERIES_LEDGER.md").write_text(ledger, encoding="utf-8")
    cfg = config(side)
    if not latitude:
        cfg["_comment_variant"] = "A/B比較用：BRIEF 第0節（裁量の条項）を外した版"
    (dest / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    corpus = dest / "guard" / "corpus"
    corpus.mkdir(parents=True)
    for src, name in [(SERIES / "Grauwall_01" / "output" / "final.md", "第1回_夜啼きの涙.md"),
                      (SERIES / "Grauwall_02" / "output" / "final_proofread.md", "第2回_新しい組合長.md")]:
        if src.exists():
            shutil.copy(src, corpus / name)
    extra = HERE / "corpus"          # 人が参考文（引き写しを見張りたい文章）を置く場所。あれば足す
    if extra.exists():
        for f in extra.glob("*"):
            if f.is_file():
                shutil.copy(f, corpus / f.name)
    for d in ["canon", "state", "chapters", "work", "work/inbox", "output", "logs", "notes", "notes/drafts", "images"]:
        (dest / d).mkdir(exist_ok=True)
    (dest / "notes" / "README.md").write_text(
        "# notes/\n\n書き手が自由に使える唯一の場所（会話の記録、案、作業ログ）。ここ以外の場所は novelctl.py が書く。\n",
        encoding="utf-8")
    subprocess.run([sys.executable, "tools/novelctl.py", "init"], cwd=dest, check=True)
    subprocess.run([sys.executable, "tools/guard.py", "seal"], cwd=dest, check=True)
    print(f"MADE: {dest.relative_to(REPO)}")
    return dest


def pack(dest):
    out = HERE / "dist"
    out.mkdir(exist_ok=True)
    tgz = out / f"{dest.name}.tar.gz"
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(dest, arcname=dest.name, filter=lambda ti: None if "__pycache__" in ti.name else ti)
    print(f"PACKED: {tgz.relative_to(REPO)}（{tgz.stat().st_size // 1024} KB）")


def main(argv):
    bible, ledger = bible_excerpt(), ledger_excerpt()
    leak_check("設定資料の抜粋", bible)
    leak_check("台帳の抜粋", ledger)
    print(f"抜粋：設定資料 {len(bible)}字 / 台帳 {len(ledger)}字。漏れ検査は通りました。")
    if "--excerpt-only" in argv:
        (HERE / "dist").mkdir(exist_ok=True)
        (HERE / "dist" / "SERIES_BIBLE_excerpt.md").write_text(bible, encoding="utf-8")
        (HERE / "dist" / "SERIES_LEDGER_excerpt.md").write_text(ledger, encoding="utf-8")
        return 0
    sides = [argv[argv.index("--only") + 1]] if "--only" in argv else list(SIDES)
    latitude = "--no-latitude" not in argv
    suffix = argv[argv.index("--suffix") + 1] if "--suffix" in argv else ("_nolat" if not latitude else "")
    for side in sides:
        dest = build(side, bible, ledger, latitude, suffix)
        if "--pack" in argv and side == "team":
            pack(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
