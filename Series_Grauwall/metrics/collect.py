#!/usr/bin/env python3
"""metrics/collect.py — グラウヴァル第一シリーズの定量の振り返り。ログ・監査・git 履歴から数字を集める。"""
import json, re, subprocess, collections, glob
from pathlib import Path
SG = Path(__file__).resolve().parent.parent; ROOT = SG.parent
EPS = [("01","夜啼きの涙","Grauwall_01","output/final.md"),("02","新しい組合長","Grauwall_02","output/final_proofread.md"),
("03","北街道の白い影","Grauwall_03_aion","output/final_proofread.md"),("04","豆のスープ","Grauwall_04","output/final.md"),
("05","隊長の非番","Grauwall_05","output/final.md"),("06","白塔の使者","Grauwall_06","output/final_proofread.md"),
("07","祝福の日","Grauwall_07","output/final_proofread.md"),("08","灰色山脈の古砦","Grauwall_08","output/final_proofread.md"),
("09","灰壁の掟","Grauwall_09","output/final_proofread.md"),("10","谷の祭り","Grauwall_10","output/final_proofread.md"),
("11","南の川港","Grauwall_11","output/final_proofread.md"),("12","十三個目の卵","Grauwall_12","output/final.md")]
def body_chars(t):
    t = "\n".join(l for l in t.splitlines() if not l.startswith("#"))
    return len(re.sub(r"\s", "", t))
def table_rows(p):
    if not p.exists(): return None
    return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if re.match(r"^\|\s*\d+", l))
def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True, text=True).stdout
def added_chars(path):
    out = git("log", "-p", "--format=", "--", path)
    return sum(len(re.sub(r"\s", "", l[1:])) for l in out.splitlines() if l.startswith("+") and not l.startswith("+++"))
def period(path):
    d = git("log", "--format=%ad", "--date=short", "--", path).split()
    return (d[-1], d[0]) if d else ("", "")
R = []; M = collections.defaultdict(lambda: collections.Counter())
for ep, title, d, fin in EPS:
    D = SG / d; r = {"ep": ep, "title": title}
    r["final_chars"] = body_chars((D/fin).read_text(encoding="utf-8"))
    r["chapters"] = len(re.findall(r"^#{1,2}\s*第\s*\d+\s*章", (D/fin).read_text(encoding="utf-8"), re.M))
    r["period"] = period(f"Series_Grauwall/{d}")
    r["git_added_chapters"] = added_chars(f"Series_Grauwall/{d}/chapters")
    r["audit_design"] = table_rows(D/"audit/report_luna.md")
    r["audit_text"] = table_rows(D/"audit/text_report_luna.md") or table_rows(D/"audit/report_manuscript_luna.md")
    r["proofread"] = table_rows(D/"audit/proofread_changes.md") or table_rows(D/"output/proofread_changes.md")
    log = D/"logs/run.log"
    if log.exists():
        L = log.read_text(encoding="utf-8").splitlines(); role = None
        drafts = collections.Counter(); fails = 0; probs = 0; first_pass = 0; first_total = 0; esc = 0; forced = 0
        for i, l in enumerate(L):
            m = re.search(r"CALL (\w+) (\S+)", l)
            if m: role = m.group(1); task = m.group(2)
            m = re.search(r"usage: in=(\d+) out=(\d+) reasoning_chars=(\d+) content_chars=(\d+) cost=([\d.]+) sec=(\d+) model=(\S+)", l)
            if m:
                k = (m.group(7), role); c = M[k]
                c["calls"] += 1; c["in"] += int(m.group(1)); c["out"] += int(m.group(2)); c["rchars"] += int(m.group(3)); c["cchars"] += int(m.group(4))
                c["cost_e9"] += int(float(m.group(5))*1e9); c["sec"] += int(m.group(6)); c["eps"] = 0
                M[(m.group(7), "_eps")][ep] += 1
                if role == "writer" and "write_ch" in task: drafts[task] += 1; c["draft_chars"] += int(m.group(4))
            m = re.search(r"CH(\d+) fail a(\d+): (\d+) problems", l)
            if m:
                fails += 1; probs += int(m.group(3))
                if m.group(2) == "1": first_total += 1
            if re.search(r"CH\d+ (pass|accepted) a1\b|CH\d+ pass\b.*a1", l): first_pass += 1; first_total += 1
            if "ESCALATE" in l: esc += 1
            if "CHAPTER_EXHAUSTED" in l and "RESOLVE" in l: forced += 1
        r.update({"log_drafts": sum(drafts.values()), "log_review_fails": fails, "log_problems": probs, "log_escalations": esc, "log_forced_accept": forced})
    R.append(r)
json.dump({"episodes": R, "models": {f"{k[0]}|{k[1]}": dict(v) for k, v in M.items()}}, open(Path(__file__).parent/"metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False)[:3000])
for k, v in M.items():
    if k[1] != "_eps": print(k, dict(v))
    else: print(k, dict(v))
