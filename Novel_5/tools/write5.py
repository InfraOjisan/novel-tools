#!/usr/bin/env python3
"""write5.py — Novel_5『星を汚す者』を、書き手ごとに章を順に書かせる（追記台帳つき）。

  python3 tools/write5.py run --writer haiku|lunapro|luna|opus_agy [--timeout 165]
  python3 tools/write5.py status
出力：runs/<writer>/chNN.md（本文）、runs/<writer>/LEDGER.md（追記台帳）、runs/<writer>/log.jsonl
opus_agy は Mac 上の agy（Antigravity CLI）を呼ぶ：agy -p "<prompt>" --model "Claude Opus 5.5"
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # Novel_5
sys.path.insert(0, str(HERE.parent / "Novel_4" / "tools"))
import team  # noqa: E402  （Novel_4 のプロバイダ設定とキーを使う）
from team import chat, rd, wr, sec  # noqa: E402

CHAPTERS = [
    (1, "発見", 3000, "着陸、掘削と採取、数週間の培養、増殖の検出と歓喜。後で効く違和感を一つ置く"),
    (2, "一致", 3500, "遺伝情報が地球の微生物と一致。滅菌記録の欠落。発見が汚染に反転する"),
    (3, "亀裂", 3500, "汚染が亀裂へ漏れた疑い。通信遅延で誰にも頼れない。責任の所在と乗員の動揺"),
    (4, "選択", 4000, "手段の検討。他の方法が足りない理由。代償が帰還不能だと分かる。決断"),
    (5, "送信", 3500, "実行。代償の現実化。記録と警告の送信。確かめきれないまま見張り続ける結末"),
]
WRITERS = {
    "haiku": {"name": "haiku", "provider": "openrouter", "api": "chat", "model": "anthropic/claude-haiku-5.5", "temperature": 0.8, "max_tokens": 16000},
    "lunapro": {"name": "lunapro", "provider": "openrouter", "api": "chat", "model": "openai/gpt-6-luna-pro", "temperature": 0.8, "max_tokens": 16000},
    "luna": {"name": "luna", "provider": "openrouter", "api": "chat", "model": "openai/gpt-6-luna", "temperature": 0.8, "max_tokens": 16000},
}


AGY_MODEL = "Claude Opus 5.5 (Medium)"


def nchar(s):
    return len(re.sub(r"\s", "", s))


def odd_chars(s):
    """日本語の文字コード（cp932）に無い漢字＝簡体字・繁体字の混入の疑い"""
    bad = []
    for ch in set(s):
        if "一" <= ch <= "鿿":
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                bad.append(ch)
    return bad


def split(out):
    m = re.search(r"^#\s*追記台帳\s*$", out, flags=re.M)
    body = out[:m.start()].strip() if m else out.strip()
    led = [l.strip()[1:].strip() for l in out[m.end():].splitlines() if l.strip().startswith("-")] if m else []
    led = [l for l in led if l and l != "なし"]
    return body, led


def call(writer, prompt, timeout):
    t0 = time.time()
    if writer == "opus_agy":
        r = subprocess.run(["agy", "-p", prompt, "--model", AGY_MODEL], capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        if not out:
            raise RuntimeError("agy の出力が空: " + r.stderr[:2000])
        return out, {"sec": round(time.time() - t0, 1), "via": "agy"}
    p = dict(WRITERS[writer], timeout_sec=timeout)
    out = chat(p, "あなたは日本語で書く小説家です。指示された形式のテキストだけを返します。", prompt, f"novel5:{writer}")
    return out, {"sec": round(time.time() - t0, 1), "via": p["model"]}


def run(a):
    d = HERE / "runs" / a.writer
    team.RUN = d
    canon = rd(HERE / "canon" / "CANON.md")
    tmpl = rd(HERE / "prompts" / "write_chapter.md")
    for n, title, chars, events in CHAPTERS:
        f = d / f"ch{n:02d}.md"
        if f.exists():
            continue
        prev = "\n\n".join(rd(d / f"ch{k:02d}.md") for k in range(1, n))
        ledger = rd(d / "LEDGER.md") or "（まだない）"
        ask = tmpl.replace("{N}", str(n)).replace("{TITLE}", title).replace("{CHARS}", str(chars)).replace("{EVENTS}", events)
        prompt = sec("CANON（薄版）", canon) + sec("追記台帳（これまでに決めたこと）", ledger) + (sec("これまでの章（全文）", prev) if prev else "") + "\n" + ask
        best, note = None, ""
        for k in range(2):
            try:
                out, meta = call(a.writer, prompt + note, a.timeout)
            except Exception as e:
                wr(d / "log.jsonl", (rd(d / "log.jsonl") or "") + json.dumps({"ch": n, "try": k + 1, "err": str(e)[:2000]}, ensure_ascii=False) + "\n")
                if "invalid model" in str(e):
                    sys.exit("agy のモデル名が違います：\n" + str(e)[:2000] + "\n→ --agy-model \"<上の一覧の名前>\" を付けて再実行")
                if "timed out" in str(e) or "Timeout" in type(e).__name__:
                    sys.exit(f"第{n}章：時間切れ（--timeout を延ばして手元で再実行）")
                continue
            body, led = split(out)
            c = nchar(body)
            issues = []
            if not (0.9 * chars <= c <= 1.1 * chars):
                issues.append(f"本文が{c}字（目標{chars}字の±10%）")
            if not body.lstrip().startswith(f"# 第{n}章"):
                issues.append("章題の行がない")
            oc = odd_chars(body)
            if oc:
                issues.append("日本語にない漢字（簡体字・繁体字の疑い）：" + "".join(oc))
            rep = team.repeated(body, n=30)
            if rep:
                issues.append(f"同じ30字の繰り返し：{rep}")
            wr(d / f"ch{n:02d}.try{k + 1}.md", out)
            wr(d / "log.jsonl", (rd(d / "log.jsonl") or "") + json.dumps({"ch": n, "try": k + 1, "chars": c, "issues": issues, **meta}, ensure_ascii=False) + "\n")
            score = len(issues) + abs(c - chars) / chars
            if best is None or score < best[0]:
                best = (score, body, led, issues)
            if not issues:
                break
            note = "\n\n（前回の原稿の問題：" + "／".join(issues) + "。直して、同じ形式で全文を書き直してください）"
        if not best:
            sys.exit(f"第{n}章：原稿が得られなかった")
        _, body, led, issues = best
        wr(f, body + "\n")
        if led:
            wr(d / "LEDGER.md", (rd(d / "LEDGER.md") or "# 追記台帳\n") + "\n".join(f"- 第{n}章｜{l}" for l in led) + "\n")
        print(f"[{a.writer}] 第{n}章 {nchar(body)}字 {'問題：' + '／'.join(issues) if issues else 'OK'}")
        if a.one:
            return
    print(f"[{a.writer}] 完了")


def revise(a):
    """校正（監査）の指摘 runs/<w>/REVIEW_r{R}.json に従い、章を順に改稿する。出力は runs/<w>/r{R}/。"""
    base = HERE / "runs" / a.writer
    team.RUN = base
    src = base if a.round == 1 else base / f"r{a.round - 1}"
    d = base / f"r{a.round}"
    review = json.loads(rd(base / f"REVIEW_r{a.round}.json"))
    canon = rd(HERE / "canon" / "CANON.md")
    tmpl = rd(HERE / "prompts" / "revise_chapter.md")
    if not (d / "LEDGER.md").exists():
        wr(d / "LEDGER.md", rd(src / "LEDGER.md") or "# 追記台帳\n")
    for n, title, chars, events in CHAPTERS:
        f = d / f"ch{n:02d}.md"
        if f.exists():
            continue
        issues = review.get(str(n), [])
        if not issues:
            wr(f, rd(src / f"ch{n:02d}.md"))
            print(f"[{a.writer}] 改稿{a.round} 第{n}章：指摘なし（そのまま）")
            continue
        chapters = "\n\n".join(rd(d / f"ch{k:02d}.md") if k < n else rd(src / f"ch{k:02d}.md") for k in range(1, 6))
        ask = (tmpl.replace("{R}", str(a.round)).replace("{N}", str(n)).replace("{TITLE}", title).replace("{CHARS}", str(chars))
               .replace("{ISSUES}", "\n".join(f"- {x}" for x in issues)))
        prompt = sec("CANON（薄版）", canon) + sec("追記台帳", rd(d / "LEDGER.md")) + sec("これまでの章（第" + str(n) + "章より前は改稿済み。以降は改稿前）", chapters) + "\n" + ask
        best, note = None, ""
        for k in range(2):
            try:
                out, meta = call(a.writer, prompt + note, a.timeout)
            except Exception as e:
                if "timed out" in str(e):
                    sys.exit(f"改稿 第{n}章：時間切れ")
                continue
            memo = ""
            m = re.search(r"^#\s*改稿メモ\s*$", out, flags=re.M)
            if m:
                memo, out = out[m.end():].strip(), out[:m.start()]
            body, led = split(out)
            c = nchar(body)
            iss = []
            if not (0.9 * chars <= c <= 1.1 * chars):
                iss.append(f"本文が{c}字（目標{chars}字の±10%）")
            if not body.lstrip().startswith(f"# 第{n}章"):
                iss.append("章題の行がない")
            oc = odd_chars(body)
            if oc:
                iss.append("日本語にない漢字：" + "".join(oc))
            wr(d / f"ch{n:02d}.try{k + 1}.md", out + "\n\n# 改稿メモ\n" + memo)
            wr(base / "log.jsonl", (rd(base / "log.jsonl") or "") + json.dumps({"round": a.round, "ch": n, "try": k + 1, "chars": c, "issues": iss, **meta}, ensure_ascii=False) + "\n")
            score = len(iss) + abs(c - chars) / chars
            if best is None or score < best[0]:
                best = (score, body, led, iss, memo)
            if not iss:
                break
            note = "\n\n（前回の原稿の問題：" + "／".join(iss) + "。直して、同じ形式で全文を書き直してください）"
        if not best:
            sys.exit(f"改稿 第{n}章：原稿が得られなかった")
        _, body, led, iss, memo = best
        wr(f, body + "\n")
        wr(d / f"ch{n:02d}.memo.md", memo + "\n")
        led = [l for l in led if l.strip("「」 ") not in ("なし",)]
        if led:
            clean = [re.sub(r"^(第\d章｜)+", "", l) for l in led]
            wr(d / "LEDGER.md", rd(d / "LEDGER.md") + "\n".join(f"- 改稿{a.round}・第{n}章｜{l}" for l in clean) + "\n")
        print(f"[{a.writer}] 改稿{a.round} 第{n}章 {nchar(body)}字 {'問題：' + '／'.join(iss) if iss else 'OK'}")
        if a.one:
            return
    print(f"[{a.writer}] 改稿{a.round} 完了")


def status(a):
    for w in list(WRITERS) + ["opus_agy"]:
        d = HERE / "runs" / w
        chs = [f"{n}:{nchar(rd(d / f'ch{n:02d}.md'))}" for n, *_ in CHAPTERS if (d / f"ch{n:02d}.md").exists()]
        print(w, chs)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("run")
    s.add_argument("--writer", required=True, choices=list(WRITERS) + ["opus_agy"])
    s.add_argument("--timeout", type=int, default=165)
    s.add_argument("--one", action="store_true", help="1章だけ書いて止まる（この環境の時間制限用）")
    s.add_argument("--agy-model", default="Claude Opus 5.5 (Medium)")
    s = sp.add_parser("revise")
    s.add_argument("--writer", required=True, choices=list(WRITERS) + ["opus_agy"])
    s.add_argument("--round", type=int, default=1)
    s.add_argument("--agy-model", default="Claude Opus 5.5 (Medium)")
    s.add_argument("--timeout", type=int, default=165)
    s.add_argument("--one", action="store_true")
    sp.add_parser("status")
    a = ap.parse_args()
    global AGY_MODEL
    AGY_MODEL = getattr(a, "agy_model", AGY_MODEL)
    {"run": run, "revise": revise, "status": status}[a.cmd](a)


if __name__ == "__main__":
    main()
