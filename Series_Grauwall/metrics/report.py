import json, re, glob, collections, statistics
from pathlib import Path
SG = Path(__file__).resolve().parent.parent
J = json.load(open(Path(__file__).parent/"metrics.json", encoding="utf-8"))
def nchars(p): return len(re.sub(r"\s", "", Path(p).read_text(encoding="utf-8", errors="ignore")))
NC = {"01":"Grauwall_01","02":"Grauwall_02","03":"Grauwall_03_aion","06":"Grauwall_06","08":"Grauwall_08","11":"Grauwall_11"}
W = {}
for ep, d in NC.items():
    wd = SG/d/"work"; per = collections.Counter(); chars = 0
    for f in glob.glob(str(wd/"ch*_draft_a*.md")):
        ch = re.search(r"ch(\d+)_draft_a(\d+)", f).group(1); per[ch] += 1; chars += nchars(f)
    design = sum(nchars(f) for f in glob.glob(str(wd/"design_a*.out")))
    W[ep] = {"chapters": len(per), "drafts": sum(per.values()), "first_pass": sum(1 for v in per.values() if v == 1),
             "max_drafts": max(per.values()) if per else 0, "draft_chars": chars, "design_out_chars": design}
# per-call rows for price regression and per-episode model stats
rows = []; E = collections.defaultdict(lambda: collections.Counter())
for ep, d in NC.items():
    log = SG/d/"logs/run.log"; role = None
    for l in log.read_text(encoding="utf-8").splitlines():
        m = re.search(r"CALL (\w+) (\S+)", l)
        if m: role, task = m.group(1), m.group(2)
        m = re.search(r"usage: in=(\d+) out=(\d+) reasoning_chars=(\d+) content_chars=(\d+) cost=([\d.]+) sec=(\d+) model=(\S+)", l)
        if m:
            i, o, rc, cc, cost, sec, model = int(m[1]), int(m[2]), int(m[3]), int(m[4]), float(m[5]), int(m[6]), m[7]
            rows.append((model, i, o, cost))
            k = (ep, model.split("/")[-1], role); c = E[k]
            c["calls"] += 1; c["in"] += i; c["out"] += o; c["rc"] += rc; c["cc"] += cc; c["cost"] += cost; c["sec"] += sec
            if "write_ch" in task: c["drafts"] += 1; c["draft_cc"] += cc
        m = re.search(r"CH\d+ fail a\d+: (\d+) problems", l)
        if m: E[(ep, "_review", "")]["fails"] += 1; E[(ep, "_review", "")]["problems"] += int(m[1])
# price per Mtok by least squares
def fit(model):
    R = [(i, o, c) for m, i, o, c in rows if m == model]
    sii = sum(i*i for i,o,c in R); soo = sum(o*o for i,o,c in R); sio = sum(i*o for i,o,c in R)
    sic = sum(i*c for i,o,c in R); soc = sum(o*c for i,o,c in R); det = sii*soo - sio*sio
    a = (sic*soo - soc*sio)/det; b = (soc*sii - sic*sio)/det
    return a*1e6, b*1e6, len(R)
PR = {m: fit(m) for m in set(r[0] for r in rows)}
X = {"in": 0, "out": 0, "n": 0}
for f in glob.glob(str(SG/"xcheck/log_*.txt")) + glob.glob(str(SG/"xcheck/r*.txt")):
    for l in open(f, encoding="utf-8"):
        m = re.search(r"ok \d+s in=(\d+) out=(\d+)", l)
        if m: X["in"] += int(m[1]); X["out"] += int(m[2]); X["n"] += 1
X["in"] += 235260 + 211063 + 47902; X["out"] += 73638 + 65909 + 12736; X["n"] += 7 + 6 + 1  # ep01・ep12・試し打ち（端末の出力から）
json.dump({"work": W, "episode_model": {"|".join(k): dict(v) for k, v in E.items()}, "price_per_Mtok": PR, "xcheck": X}, open(Path(__file__).parent/"metrics2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(W, ensure_ascii=False)); print(PR); print(X)
for k, v in sorted(E.items()): print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})
