#!/usr/bin/env python3
"""mx.py — ミステリ工房の実験 mx01：真相台帳の検査と、視点人物への投影

  python3 tools/mx.py check            真相台帳の制約検査        → out/author/CHECK_REPORT.md
  python3 tools/mx.py timeline         作者用のタイムライン図     → out/author/TIMELINE.md / TIMELINE.html
  python3 tools/mx.py project          書き手パケット            → out/packets/chNN_writer.md
  python3 tools/mx.py leak FILE...     真相語の漏れ検査（書き手パケット・読者パケット用）
  python3 tools/mx.py verify N FILE    章の原稿が固定の台詞・時刻を守ったか
  python3 tools/mx.py reader N         第N章までを読んだ読者役のパケット → out/reader/after_chNN.md
  python3 tools/mx.py pack writer N    書き手に渡す箱 → dist/writer_chNN/（パケット・依頼文・前の章だけ。漏れ検査つき）
  python3 tools/mx.py pack reader N    読者役に渡す箱 → dist/reader_chNN/
  python3 tools/mx.py all              check → timeline → project → leak

真相台帳は truth/WORLD.yaml。out/author/ と truth/ は作者だけが見る。
書き手（第1・2章）と読者役に渡すのは out/packets/ と out/reader/ だけ。
"""
import sys, os, re, html, itertools
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = yaml.safe_load(open(os.path.join(ROOT, "truth", "WORLD.yaml"), encoding="utf-8"))
META, PLACES, ENT, OBJ = W["meta"], W["places"], W["entities"], W.get("objects", {})
EVENTS = {e["id"]: e for e in W["events"]}
PERC = {p["id"]: p for p in W["perceptions"]}
STMT = {s["id"]: s for s in W["statements"]}
BS = {b["id"]: b for b in W.get("blind_spots", [])}
DAYS = list(META["days"].keys())
VP = META["viewpoint"]
SOL = META["solution_chapter"]
OUT = os.path.join(ROOT, "out")

# ---------------------------------------------------------------- 時刻
def hm(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)

def span(t):
    a, b = t.split("-"); return hm(a), hm(b)

def dkey(day, minute):
    return (DAYS.index(day), minute)

KAN = "〇一二三四五六七八九十"
def kan(n):
    return KAN[n] if n <= 10 else "十" + KAN[n - 10]

def bellname(h):
    h12 = h % 12 or 12
    if h == 12: return "昼の鐘"
    if h in (0, 24): return "夜半の鐘"
    return f"{kan(h12)}つの鐘" if h12 <= 9 else f"{kan(h12)}の鐘"

def bell(m):
    h, mm = divmod(m, 60)
    if mm == 0: return f"{bellname(h)}"
    if mm == 30:
        b = bellname(h)
        return f"{b.replace('の鐘', '')}半の一打" if b.endswith("つの鐘") else f"{b}から半刻の一打"
    if mm < 30: return f"{bellname(h)}のあと"
    return f"{bellname(h + 1)}の前"

def fmt(m): return f"{m // 60:02d}:{m % 60:02d}"

# ---------------------------------------------------------------- 道のり
INF = 10 ** 9
DIST = {a: {b: (0 if a == b else INF) for b in PLACES} for a in PLACES}
for a, b, w in W["edges"]:
    DIST[a][b] = DIST[b][a] = min(DIST[a][b], w)
for k, i, j in itertools.product(PLACES, PLACES, PLACES):
    if DIST[i][k] + DIST[k][j] < DIST[i][j]:
        DIST[i][j] = DIST[i][k] + DIST[k][j]
VIS = W.get("visibility", {})

def visible(frm, to):
    return frm == to or to in VIS.get(frm, [])

# ---------------------------------------------------------------- 所在
def presence(who):
    out = []
    for e in W["events"]:
        if who in e["actors"]:
            a, b = span(e["t"]); out.append((DAYS.index(e["day"]), a, b, e["place"], e["id"]))
    return sorted(out)

def at(who, day, minute, place=None):
    """その時刻にいた場所（place を渡せば、そこにいたか）"""
    for d, a, b, p, eid in presence(who):
        if d == DAYS.index(day) and a <= minute <= b and (place is None or p == place):
            return p
    return None

# ---------------------------------------------------------------- 判定の道具
def name(x): return ENT[x]["name"] if x in ENT else x
KIND = {"human": "人間"}
def kind(x): return KIND.get(ENT[x]["kind"], ENT[x]["kind"])
def demi(x): return ENT.get(x, {}).get("demihuman", False)
NAME2ID = {v["name"]: k for k, v in ENT.items()}

def role_unique(x):
    r = ENT[x].get("role")
    return r and sum(1 for v in ENT.values() if v.get("role") == r) == 1

def acts(pred):
    for e in W["events"]:
        for a in e.get("acts", []):
            if pred(e, a): yield e, a

def eval_claim(c):
    t = c.get("type")
    if t in (None, "none", "opinion"): return None
    if t == "events": return all(r in EVENTS for r in c["refs"])
    if t == "report":
        r = STMT.get(c["ref"]); return r is not None
    if t == "relay":
        e = EVENTS.get(c["before_event"])
        return bool(e) and any(a.get("by") == c["from"] and a.get("verb") == "message" for a in e.get("acts", []))
    if t == "expr":
        return bool(eval(c["expr"], {}, {"E": ENT, "O": OBJ}))
    if t == "copresence":
        m = hm(c["t"])
        return any(e["day"] == c["day"] and e["place"] == c["place"] and span(e["t"])[0] <= m <= span(e["t"])[1]
                   and set(c["actors"]) <= set(e["actors"]) for e in W["events"])
    if t == "action":
        return any(True for _ in acts(lambda e, a: e["day"] == c["day"] and a.get("by") == c["by"]
                                      and a.get("verb") == c["verb"] and (c.get("to") is None or a.get("to") == c["to"])))
    if t == "no_joint":
        return not any(e["day"] in c["days"] and c["a"] in e["actors"] and c["b"] in e["actors"] for e in W["events"])
    if t == "no_act":
        return not any(True for _ in acts(lambda e, a: a.get("verb") == c["verb"]
                                          and (c.get("by") is None or a.get("by") == c["by"])
                                          and (c.get("to") is None or a.get("to") == c["to"])))
    if t == "who_at":
        w0, w1 = span(c["window"]); seen = set()
        for e in W["events"]:
            a, b = span(e["t"])
            if e["day"] in c["days"] and e["place"] == c["place"] and a <= w1 and b >= w0:
                seen |= set(e["actors"])
        return seen == set(c["set"])
    raise ValueError(f"知らない claim の形: {t}")

def can_lie(s):
    sp = ENT[s["speaker"]]
    if sp.get("demihuman"): return False, "月影の戒め"
    if sp.get("oath_master"): return True, "誓約の主"
    if sp.get("member") and PLACES[s["place"]]["interior"] and not s.get("exception"):
        if any(ENT.get(t, {}).get("member") for t in s.get("to", [])):
            return False, "鉄の誓約（建物の中・仲間へ）"
    return True, "縛りなし"

def ptime(p):
    """知覚の時刻：出来事の始まりか、観測者がそこへ来た時刻の遅いほう"""
    e = EVENTS[p["event"]]; a, b = span(e["t"])
    hit = [s0 for d, s0, s1, pl, _ in presence(p["observer"])
           if d == DAYS.index(e["day"]) and s0 <= b and s1 >= a and visible(pl, e["place"])]
    return max([a] + sorted(hit)[:1])

def vp_items(upto=None, only=None):
    """視点人物が受け取った知覚と言明（章つき）"""
    items = []
    for p in W["perceptions"]:
        if p["observer"] == VP and p.get("chapter"):
            items.append(("P", p))
    for s in W["statements"]:
        if s.get("chapter") and (VP in s.get("heard_by", []) or s["speaker"] == VP):
            items.append(("S", s))
    def ch(x): return x[1]["chapter"]
    if upto is not None: items = [x for x in items if ch(x) <= upto]
    if only is not None: items = [x for x in items if ch(x) == only]
    def key(x):
        o = x[1]
        if x[0] == "P":
            return dkey(EVENTS[o["event"]]["day"], ptime(o))
        return dkey(o["day"], hm(o["t"]))
    return sorted(items, key=key)

# ---------------------------------------------------------------- check
def check():
    err, warn, info = [], [], []
    # 参照
    for e in W["events"]:
        if e["place"] not in PLACES: err.append(f"{e['id']}: 場所 {e['place']} がない")
        for a in e["actors"]:
            if a not in ENT: err.append(f"{e['id']}: 人物 {a} がない")
    # 所在と移動
    for who in ENT:
        pr = presence(who)
        for x, y in zip(pr, pr[1:]):
            if x[0] != y[0] or x[3] == y[3]: continue
            if y[1] < x[2]:
                err.append(f"{name(who)}: {DAYS[x[0]]} {fmt(y[1])} に {x[4]}({PLACES[x[3]]['name']}) と {y[4]}({PLACES[y[3]]['name']}) の二か所にいる")
            elif y[1] - x[2] < DIST[x[3]][y[3]]:
                err.append(f"{name(who)}: {x[4]}→{y[4]} の移動 {y[1]-x[2]}分 < 道のり {DIST[x[3]][y[3]]}分")
    # 知覚
    for p in W["perceptions"]:
        e = EVENTS.get(p["event"])
        if not e: err.append(f"{p['id']}: 出来事 {p['event']} がない"); continue
        o = p["observer"]; a, b = span(e["t"])
        hit = [s0 for d, s0, s1, pl, _ in presence(o)
               if d == DAYS.index(e["day"]) and s0 <= b and s1 >= a and visible(pl, e["place"])]
        ok = bool(hit); pt = max([a] + hit[:1])   # 観測した時刻（観測者が来た時刻か、出来事の始まり）
        if not ok: err.append(f"{p['id']}: {name(o)} は {e['id']}（{e['day']} {e['t']} {PLACES[e['place']]['name']}）を見られる所にいない")
        for tgt, label in (p.get("sees") or {}).items():
            if tgt not in e["actors"]:
                err.append(f"{p['id']}: {name(tgt)} は {e['id']} にいない"); continue
            O = ENT[o]
            if label == name(tgt):
                if demi(tgt) and not (O.get("distinguishes") or tgt in O.get("knows", [])):
                    if p.get("grounds") == "role" and role_unique(tgt): pass
                    elif O.get("assumes", {}).get(ENT[tgt]["kind"]) == tgt: pass
                    else: warn.append(f"{p['id']}: 見分けられない {name(o)} が {label} を名で当てている（根拠なし）")
            elif label.startswith("?:"):
                g = p.get("grounds", "")
                told = g.startswith("told:") and g[5:] in STMT and o in STMT[g[5:]].get("heard_by", []) \
                    and dkey(STMT[g[5:]]["day"], hm(STMT[g[5:]]["t"])) <= dkey(e["day"], pt)
                if not (O.get("distinguishes") or tgt in O.get("knows", []) or told):
                    err.append(f"{p['id']}: {name(o)} は鴉人を見分けられないのに『別人』と知覚している")
            elif label in NAME2ID:
                bs = BS.get(p.get("blind_spot", ""))
                if not (bs and bs["target"] == tgt and bs["perceived_as"] == NAME2ID[label] and o in bs["applies_to"]):
                    err.append(f"{p['id']}: {name(o)} が {name(tgt)} を {label} と取り違えているが、宣言した死角で説明されない")
                else:
                    info.append(f"{p['id']}: 取り違え {name(o)}：{name(tgt)}→{label}（{bs['id']}・{bs['axis']}）{e['day']} {bell(a)}")
    if len(BS) > META.get("max_blind_spots", 99):
        err.append(f"死角が {len(BS)} 個（上限 {META['max_blind_spots']}）")
    # 言明
    for s in W["statements"]:
        m = hm(s["t"])
        if not at(s["speaker"], s["day"], m, s["place"]):
            err.append(f"{s['id']}: 話し手 {name(s['speaker'])} が {s['day']} {s['t']} に {PLACES[s['place']]['name']} にいない")
        for h in s.get("heard_by", []):
            if not at(h, s["day"], m, s["place"]):
                warn.append(f"{s['id']}: 聞き手 {name(h)} がその場にいない")
        truth = eval_claim(s.get("claim", {}))
        lie_ok, why = can_lie(s)
        if truth is False:
            basis = [PERC[b] for b in s.get("basis", []) if b in PERC]
            if basis and all(b["observer"] == s["speaker"] and b.get("blind_spot") for b in basis):
                info.append(f"{s['id']}: {name(s['speaker'])} の言明は事実と違うが、死角 {basis[0]['blind_spot']} による誤信（嘘ではない）：{s['text']}")
            elif not lie_ok:
                err.append(f"{s['id']}: {name(s['speaker'])} は嘘をつけない（{why}）のに偽の言明：{s['text']}")
            else:
                warn.append(f"{s['id']}: 嘘（{name(s['speaker'])}・{why}）：{s['text']}")
        # 解決章より前に、視点人物が真相の名を聞いてはいけない
        if s.get("chapter", 99) < SOL and VP in s.get("heard_by", []):
            for k, v in ENT.items():
                if v.get("hidden") and v["name"] in s["text"]:
                    err.append(f"{s['id']}: 解決章より前に、視点人物が真相の名『{v['name']}』を聞く")
    # 視点人物の知覚に、解決章より前で真相が混ざっていないか
    for k, p in vp_items():
        if k == "P" and p["chapter"] < SOL:
            for tgt, label in (p.get("sees") or {}).items():
                if ENT[tgt].get("hidden") and (label == name(tgt) or label.startswith("?:")):
                    err.append(f"{p['id']}: 解決章より前に、視点人物が真相の人物を見分けている")
    # フェアプレイ
    acc, ferr = {}, []
    for k, o in vp_items(): acc[o["id"]] = o["chapter"]
    for c in W["solution"]["clues"]:
        if c["chapter"] >= SOL: ferr.append(f"{c['id']}: 手がかりが解決章以降（第{c['chapter']}章）")
        for r in c["refs"]:
            if r not in acc: ferr.append(f"{c['id']}: {r} は視点人物に届いていない（読者に見えない）")
            elif acc[r] > c["chapter"]: ferr.append(f"{c['id']}: {r} は第{acc[r]}章（宣言は第{c['chapter']}章）")
    err += ferr
    if not ferr: info.append(f"フェアプレイ：手がかり {len(W['solution']['clues'])} 本は、すべて第{SOL - 1}章までに視点人物へ届く")
    # 誰も見ていない出来事（場所・時間の空白）
    seen = {p["event"] for p in W["perceptions"]}
    for e in W["events"]:
        if e["id"] not in seen and any(ENT[a].get("hidden") for a in e["actors"]):
            info.append(f"観測なし：{e['id']} {e['day']} {e['t']} {PLACES[e['place']]['name']}（{', '.join(name(a) for a in e['actors'])}：{e['action']}）")
    # 書き出し
    os.makedirs(os.path.join(OUT, "author"), exist_ok=True)
    lines = [f"# 検査報告 {META['id']}『{META['title']}』", "",
             f"- 出来事 {len(EVENTS)} / 知覚 {len(PERC)} / 言明 {len(STMT)} / 死角 {len(BS)}（上限 {META['max_blind_spots']}）",
             f"- **ERROR {len(err)} / WARN {len(warn)}**", ""]
    for title, xs in (("ERROR", err), ("WARN", warn), ("INFO", [i for i in info if i])):
        lines += [f"## {title}", ""] + [f"- {x}" for x in xs] + ([] if xs else ["- なし"]) + [""]
    open(os.path.join(OUT, "author", "CHECK_REPORT.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(f"check: ERROR {len(err)} / WARN {len(warn)} / INFO {len([i for i in info if i])}")
    for x in err: print("  ERROR", x)
    for x in warn: print("  WARN ", x)
    return not err

# ---------------------------------------------------------------- timeline
def timeline():
    os.makedirs(os.path.join(OUT, "author"), exist_ok=True)
    obs = {}
    for p in W["perceptions"]:
        obs.setdefault(p["event"], []).append(p)
    md = [f"# タイムライン（作者のみ）{META['id']}『{META['title']}』", ""]
    for d in DAYS:
        md += [f"## {d}　{META['days'][d]}", "", "| 時刻 | 鐘 | 場所 | 誰 | 何 | 観測（呼び名） |", "|---|---|---|---|---|---|"]
        for e in sorted([e for e in W["events"] if e["day"] == d], key=lambda e: span(e["t"])):
            a, b = span(e["t"])
            o = "；".join(f"{name(p['observer'])}→" + "・".join(p.get("sees", {}).values() or ["（物）"])
                         + (f"〔{p['blind_spot']}〕" if p.get("blind_spot") else "") for p in obs.get(e["id"], []))
            hidden = "★" if e.get("truth_only") or not obs.get(e["id"]) else ""
            md.append(f"| {e['t']} | {bell(a)} | {PLACES[e['place']]['name']} | {'・'.join(name(x) for x in e['actors'])} | {hidden}{e['action']} | {o or '—（誰も見ていない）'} |")
        md.append("")
    md += ["★＝誰も見ていない、または真相側だけの出来事", ""]
    open(os.path.join(OUT, "author", "TIMELINE.md"), "w", encoding="utf-8").write("\n".join(md))
    # HTML（人物×時間）
    colors = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#76b7b2", "#edc948", "#9c755f", "#e15759", "#bab0ac", "#86bcb6"]
    pc = {p: colors[i % len(colors)] for i, p in enumerate(PLACES)}
    parts = []
    windows = []
    for d in DAYS:   # 店番のような長い背景の出来事は除き、間が九十分以上あけば窓を分ける
        evs = sorted([e for e in W["events"] if e["day"] == d and span(e["t"])[1] - span(e["t"])[0] <= 300], key=lambda e: span(e["t"]))
        cur, end = [], -1
        for e in evs:
            a, b = span(e["t"])
            if cur and a - end > 90: windows.append((d, cur)); cur = []
            cur.append(e); end = max(end, b) if cur[:-1] else b
        if cur: windows.append((d, cur))
    for d, evs in windows:
        t0 = min(span(e["t"])[0] for e in evs) // 15 * 15 - 15
        t1 = max(span(e["t"])[1] for e in evs) // 15 * 15 + 15
        rows = [k for k in ENT if any(k in e["actors"] for e in evs)]
        PX, RH, LW = 7, 30, 96
        wpx = LW + (t1 - t0) * PX + 20; hpx = 36 + RH * len(rows) + 10
        x = lambda m: LW + (m - t0) * PX
        y = {r: 36 + i * RH for i, r in enumerate(rows)}
        s = [f'<h2>{d}　{META["days"][d]}　{fmt(t0+15)}〜</h2><div class="scroll"><svg width="{wpx}" height="{hpx}" role="img">']
        for m in range(t0, t1 + 1, 15):
            s.append(f'<line x1="{x(m)}" y1="28" x2="{x(m)}" y2="{hpx-6}" class="{"hr" if m % 60 == 0 else "q"}"/>')
            if m % 30 == 0: s.append(f'<text x="{x(m)+2}" y="20" class="tick">{fmt(m)}{" "+bellname(m//60) if m%60==0 else ""}</text>')
        for r in rows:
            cls = "hid" if ENT[r].get("hidden") else "lbl"
            s.append(f'<text x="6" y="{y[r]+18}" class="{cls}">{name(r)}</text>')
        for e in evs:
            a, b = span(e["t"])
            tip = html.escape(f"{e['id']} {e['t']} {PLACES[e['place']]['name']}：{e['action']}")
            for r in e["actors"]:
                s.append(f'<rect x="{x(a)}" y="{y[r]+5}" width="{max(3,(b-a)*PX)}" height="{RH-10}" rx="3" fill="{pc[e["place"]]}" opacity="{0.55 if e.get("truth_only") else 0.9}"><title>{tip}</title></rect>')
        for p in W["perceptions"]:
            e = EVENTS[p["event"]]
            if e["day"] != d or p["observer"] not in y or not (t0 <= span(e["t"])[0] <= t1): continue
            a, _ = span(e["t"])
            for tgt, label in (p.get("sees") or {}).items():
                if tgt in y and tgt != p["observer"]:
                    bs = p.get("blind_spot")
                    s.append(f'<line x1="{x(a)+2}" y1="{y[p["observer"]]+15}" x2="{x(a)+2}" y2="{y[tgt]+15}" class="{"bs" if bs else "ob"}"><title>{html.escape(name(p["observer"])+"→"+label+("〔"+bs+"〕" if bs else ""))}</title></line>')
        s.append("</svg></div>")
        parts.append("".join(s))
    legend = "".join(f'<span><i style="background:{pc[p]}"></i>{html.escape(v["name"])}</span>' for p, v in PLACES.items())
    page = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>真相タイムライン</title><style>
:root{{--bg:#fbfaf7;--fg:#222;--mut:#888;--line:#ddd;--hid:#c0392b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16171a;--fg:#e8e6e1;--mut:#9a9a9a;--line:#33363b;--hid:#ff7b6b}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.6 "Hiragino Sans","Noto Sans JP",sans-serif;margin:0;padding:16px}}
.scroll{{overflow-x:auto}} svg text{{fill:var(--fg)}} .tick{{font-size:11px;fill:var(--mut)}} .lbl{{font-size:13px}} .hid{{font-size:13px;fill:var(--hid);font-weight:700}}
line.hr{{stroke:var(--line)}} line.q{{stroke:var(--line);stroke-dasharray:2 4}} line.ob{{stroke:var(--mut);stroke-width:1.5}} line.bs{{stroke:var(--hid);stroke-width:2.5;stroke-dasharray:4 3}}
.legend span{{display:inline-flex;align-items:center;margin:0 12px 6px 0;font-size:12px}} .legend i{{width:12px;height:12px;border-radius:3px;margin-right:4px;display:inline-block}}
</style><h1>真相タイムライン（作者のみ）— {html.escape(META['title'])}</h1>
<p>帯＝その人物がいた場所（色）。淡い帯＝誰も見ていない真相側の出来事。縦線＝観測（灰）、<span style="color:var(--hid)">赤の破線＝死角による取り違え</span>。赤字の人物は視点人物が解決まで存在を知らない。</p>
<div class="legend">{legend}</div>{''.join(parts)}</html>"""
    open(os.path.join(OUT, "author", "TIMELINE.html"), "w", encoding="utf-8").write(page)
    print("timeline: out/author/TIMELINE.md, TIMELINE.html")

# ---------------------------------------------------------------- project
RULES = """\
1. **このパケットに書かれていることが、ダリオの知っていることのすべてです。** ここに無い出来事・人物・事情を足さないでください。
2. 地の文は、ダリオが見たこと・聞いたことだけを書きます。ダリオのいない場所の出来事は、人の口から語られたときだけ、台詞として書きます。
3. 地の文は嘘をつきません。「見たこと」に書かれた呼び名で人を呼んでください。ダリオの思い込みは「〜だろう」「〜に違いない」と、ダリオの考えとして書きます。
4. 「台詞」の欄の言葉は**一字一句そのまま**使います（前後に別の台詞を足すのは自由）。台詞の中身を言い換えたり、説明を足したりしないでください。
5. 時刻は鐘で書きます（「七つの鐘」「八つの鐘のあと」）。パケットにある鐘の刻を動かさないでください。
6. ダリオの推理は、「章末のダリオの見立て」の範囲までにします。ダリオにそれ以上の結論を出させないでください。パケットの中に食い違って見えることがあっても、書き手が辻褄を合わせたり、理由を作ったりしないでください（そのまま書く）。
7. 手がかりらしい一文で段落を締めない。大事なことほど、冗談や雑談の中にさりげなく置く。
8. 本文に管理用語（パケット、場面番号、P_、S0、手がかり、伏線 など）を書かない。
"""

def label_for_narration(p, tgt, label):
    O = ENT[p["observer"]]
    if label.startswith("?:"): return label[2:]
    if label == name(tgt): return label
    if label in NAME2ID:   # 取り違え：地の文は種族名で、思い込みは考えとして
        return f"{kind(tgt)}（{name(p['observer'])}は{label}だと思った）"
    return label

def known_cast(upto):
    who = set()
    for k, o in vp_items(upto=upto):
        if k == "P":
            for tgt, label in (o.get("sees") or {}).items():
                if label.startswith("?:") or label not in NAME2ID or NAME2ID.get(label) == tgt:
                    if label == name(tgt): who.add(tgt)
                else: who.add(NAME2ID[label])
        else:
            who.add(o["speaker"]); who |= set(o.get("to", []))
            who |= {k for k, v in ENT.items() if v["name"] in o["text"]}
    who.add(VP)
    return [w for w in ENT if w in who and (upto >= SOL or not ENT[w].get("hidden"))]

def scenes(items):
    out, cur, last = [], [], None
    for k, o in items:
        if k == "P":
            e = EVENTS[o["event"]]; d, m, pl = e["day"], ptime(o), e["place"]
        else:
            d, m, pl = o["day"], hm(o["t"]), o["place"]
        if last and (d != last[0] or (pl != last[2] and not visible(pl, last[2])) or m - last[1] > 25):
            out.append(cur); cur = []
        cur.append((k, o, d, m, pl)); last = (d, m, pl)
    if cur: out.append(cur)
    return out

def packet(n):
    ch = W["chapters"][n]
    items = vp_items(only=n)
    L = [f"# 執筆パケット　第{n}章「{ch['title']}」", ""]
    if n < SOL:
        L += ["> このパケットだけを見て書いてください。ここに無いことは、ダリオも書き手も知りません。", ""]
    else:
        L += ["> 解決章です。第4節に、解決で明かす事実があります。", ""]
    L += ["## 0. 作品", "",
          f"- {META['series']}。時期：{META['period']}",
          f"- ジャンル：{META['genre']}", f"- 語り：{META['narration']}",
          f"- 長さ：約{ch['target_chars']}字（日本語）", f"- 前の章がある場合は、その本文（chapters/）を読んでから続けてください。", "",
          "## 1. 書き方の規則", "", RULES,
          "グラウヴァルの決まり（本文で必要なら使う）：組合の建物の中では、組合員は仲間に嘘をつけない（鉄の誓約）。例外は、組合長に言えと命じられたこと（長の命）、金を受け取った相手のため（代価）、酒が入っているとき（酒精）の三つだけ。亜人は、どこでも嘘をつけない。黙る・はぐらかす・問いで返すことはできる。人間の多くは、同じ種族の亜人を一人一人見分けない。時刻は大聖堂の鐘（一刻ごとに刻の数だけ鳴り、半刻に一打）。", "",
          "## 2. 登場人物（ダリオの知っている範囲）", ""]
    for w in known_cast(n):
        L.append(f"- **{name(w)}**（{kind(w)}）：{ENT[w]['attrs'].get('desc', '')}"
                 + (f"。{ENT[w]['attrs']['arm']}" if 'arm' in ENT[w]['attrs'] else ""))
    sp = ch['span']
    for d in DAYS: sp = sp.replace(d + " ", META["days"][d] + " ")
    L += ["", f"## 3. 場面（時刻順・{sp}）", "", f"章の役目：{ch['function'].strip()}", ""]
    for i, sc in enumerate(scenes(items), 1):
        d, m, pl = sc[0][2], sc[0][3], sc[0][4]
        L.append(f"### 場面{i}　{META['days'][d]}　{bell(m)}ごろ　{PLACES[pl]['name']}")
        for k, o, d2, m2, pl2 in sc:
            if k == "P":
                e = EVENTS[o["event"]]
                who = "、".join(label_for_narration(o, t, lb) for t, lb in (o.get("sees") or {}).items() if t != VP)
                L.append(f"- 見たこと（{bell(ptime(o))}）{('［' + who + '］') if who else ''}")
                for nt in o.get("notes", []): L.append(f"    - {nt}")
            else:
                ctx = f"（{o['context']}）" if o.get("context") else ""
                to = "・".join(name(t) for t in o.get("to", []))
                L.append(f"- 台詞（{bell(m2)}）{name(o['speaker'])}→{to}{ctx}：{o['text']}")
        L.append("")
    if n < SOL:
        L += ["## 4. 章末のダリオの見立て", ""] + [f"- {b}" for b in ch.get("beliefs_end", [])] + [""]
    else:
        S = W["solution"]; kiri = [k for k, v in ENT.items() if v.get("hidden")]
        L += ["## 4. 解決で明かす事実", "",
              f"- だれ：{S['answer']['who']}", f"- どうやって：{S['answer']['how']}",
              f"- 嘘：{S['answer']['lie']}", f"- なぜ（軽く）：{S['answer']['why_light'].strip()}", ""]
        for k in kiri:
            a = ENT[k]["attrs"]
            L.append(f"- **{name(k)}**：{a.get('desc')}。{a.get('relation')}。足は{a.get('feet')}、羽根は{a.get('feather')}。三ずつ数える。{a.get('wish')}")
        L += ["", "### エーリカの推理に使う手がかり（すべて第1・2章に出ている。新しい証拠を出さない）", ""]
        L += [f"- 第{c['chapter']}章：{c['text']}" for c in S["clues"]]
        L += ["", "### 探偵が見たこと（ダリオには見えない。本人の台詞として語らせる）", ""]
        for p in sorted([p for p in W["perceptions"] if p.get("chapter") == n and p["observer"] != VP], key=lambda p: ptime(p)):
            e = EVENTS[p["event"]]
            who = "、".join(label_for_narration(p, t, lb) for t, lb in (p.get("sees") or {}).items())
            L.append(f"- {name(p['observer'])}（{bell(ptime(p))}・{PLACES[e['place']]['name']}）［{who}］：" + "／".join(p.get("notes", [])))
        L += ["", "- エーリカは見分ける。ダリオは見分けない。エーリカは推理を述べたあと、中庭と二階で確かめる。"]
    L += ["", "## 5. 自由にしてよいこと", ""] + [f"- {f}" for f in ch.get("free", [])]
    L += ["- 天気、店の物音、食べ物、人物の癖、どうでもいい会話（ただし規則1・2の範囲で）", "",
          "## 6. 出力形式", "", f"- 1行目に `# 第{n}章　{ch['title']}`。2行目以降が本文。", "- 場面転換は空行のあとに `＊` だけの行。",
          "- 本文以外（前置き、解説、要約、箇条書き）は書かない。", ""]
    return "\n".join(L)

def project():
    os.makedirs(os.path.join(OUT, "packets"), exist_ok=True)
    for n in W["chapters"]:
        p = os.path.join(OUT, "packets", f"ch{n:02d}_writer.md")
        open(p, "w", encoding="utf-8").write(packet(n))
        print(f"project: {os.path.relpath(p, ROOT)}" + ("（真相を含む：解決章）" if n >= SOL else ""))

# ---------------------------------------------------------------- leak / verify / reader
def leak(files):
    bad = 0
    for f in files:
        t = open(f, encoding="utf-8").read()
        hits = [w for w in META["leak_tokens"] if w in t]
        if hits: bad += 1; print(f"LEAK {f}: {hits}")
        else: print(f"ok   {f}")
    return bad == 0

def verify(n, f):
    t = open(f, encoding="utf-8").read(); ok = True
    for k, o in vp_items(only=n):
        if k == "S":
            core = o["text"].strip("『』")
            if core.replace("〈", "『").replace("〉", "』") not in t and core not in t:
                ok = False; print(f"台詞なし {o['id']} {name(o['speaker'])}：{o['text']}")
    for k, o in vp_items(only=n):   # 鐘の刻（時刻の固定）
        m = span(EVENTS[o["event"]]["t"])[0] if k == "P" else hm(o["t"])
        if m % 60 == 0 and 17 * 60 <= m <= 21 * 60:
            b = bellname(m // 60).replace("の鐘", "")
            if b not in t: ok = False; print(f"鐘なし {o['id']}：『{b}』が本文にない")
    if n < SOL:
        hits = [w for w in META["leak_tokens"] if w in t]
        if hits: ok = False; print(f"真相語 {hits}")
    print("verify:", "ok" if ok else "NG"); return ok

READER_Q = """\
次の問いに、本文だけを根拠に答えてください。分からないことは「分からない」と書き、推測なら推測と書いてください。
答えは JSON で：
{
  "q1_rina_doing": "リナは毎晩、七つの鐘のころ何をしているか",
  "q2_with_whom": "厩の二階でリナと一緒にいるのは誰か",
  "q3_did_rina_lie": "リナはフーゴに嘘をついたか（はい／いいえ／分からない）と、その理由",
  "q4_confidence": 0から100（q2の確信度）,
  "q5_evidence": ["根拠にした本文の一文（そのまま引用）", "..."],
  "q6_odd_points": ["引っかかったが説明できない点", "..."]
}
"""

def reader(n):
    os.makedirs(os.path.join(OUT, "reader"), exist_ok=True)
    L = [f"# 読者役パケット（第{n}章まで）", "",
         "あなたはミステリの読者です。作者の設定資料・パケットは見ていません。下の本文だけを読んでください。", "",
         READER_Q, "", "---", ""]
    for i in range(1, n + 1):
        p = os.path.join(ROOT, "chapters", f"ch{i:02d}.md")
        L += [open(p, encoding="utf-8").read() if os.path.exists(p) else f"（chapters/ch{i:02d}.md がまだありません）", ""]
    out = os.path.join(OUT, "reader", f"after_ch{n:02d}.md")
    open(out, "w", encoding="utf-8").write("\n".join(L)); print("reader:", os.path.relpath(out, ROOT))
    key = [f"# 読者審査の合格条件（作者のみ）", ""]
    for c, m in W["solution"]["misreadings"].items():
        key.append(f"- 第{c}章のあとに起こしたい誤読：{m}")
    fz = W["solution"]["fairness"]
    key += ["", f"- 第{fz['must_not_solve_after']}章のあとで q2 に『コル以外の鴉人』と答え、q4≧70 なら **早すぎる看破（不合格）**",
            f"- 第{fz['solvable_after']}章のあとで、手がかり K1〜K8 から『鴉人は二人』と推理しうること（読者役の q6 に K1/K2 の食い違いが挙がれば良い兆し）",
            f"- 解決章のあと：読者役に第1・2章を読み返させ、手がかりが『確かに書いてあった』かを K ごとに判定させる"]
    open(os.path.join(OUT, "author", "READER_KEY.md"), "w", encoding="utf-8").write("\n".join(key))

# ---------------------------------------------------------------- pack（渡す物だけを別の箱に）
def pack(kind, n):
    """書き手・読者役に渡す箱を dist/ に作る。真相のある truth/ と out/author/ は入れない"""
    import shutil
    d = os.path.join(ROOT, "dist", f"{kind}_ch{n:02d}")
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(os.path.join(d, "chapters"))
    files = []
    if kind == "writer":
        if n >= SOL: print("pack: 解決章のパケットには真相が入っています（別の書き手に渡す）")
        shutil.copy(os.path.join(OUT, "packets", f"ch{n:02d}_writer.md"), os.path.join(d, "PACKET.md"))
        open(os.path.join(d, "WRITER.md"), "w", encoding="utf-8").write(f"""# 依頼文

あなたは小説の書き手です。このフォルダの `PACKET.md`（執筆パケット）と、前の章の本文（`chapters/` にあれば）だけを読んで、第{n}章を書いてください。

- パケットに無いことは、あなたも視点人物も知りません。足さないでください。
- パケットの中で辻褄が合わないように見えることがあっても、直したり、理由を作ったりしないでください。そのまま書いてください。
- 台詞の欄の言葉は一字一句そのまま使ってください。
- 出力は本文だけ（1行目が `# 第{n}章　{W['chapters'][n]['title']}`）。書いた本文は `chapters/ch{n:02d}.md` に置いてください。
""")
        for i in range(1, n):
            src = os.path.join(ROOT, "chapters", f"ch{i:02d}.md")
            if os.path.exists(src): shutil.copy(src, os.path.join(d, "chapters"))
        files = [os.path.join(d, "PACKET.md"), os.path.join(d, "WRITER.md")]
    else:
        reader(n)
        shutil.copy(os.path.join(OUT, "reader", f"after_ch{n:02d}.md"), os.path.join(d, "READER.md"))
        files = [os.path.join(d, "READER.md")]
    files += [os.path.join(d, "chapters", f) for f in os.listdir(os.path.join(d, "chapters"))]
    if n < SOL and not leak(files):
        shutil.rmtree(d); print("pack: 漏れがあったので箱を消しました"); return False
    print("pack:", os.path.relpath(d, ROOT)); return True

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "check": sys.exit(0 if check() else 1)
    elif cmd == "timeline": timeline()
    elif cmd == "project": project()
    elif cmd == "leak": sys.exit(0 if leak(sys.argv[2:]) else 1)
    elif cmd == "verify": sys.exit(0 if verify(int(sys.argv[2]), sys.argv[3]) else 1)
    elif cmd == "reader": reader(int(sys.argv[2]))
    elif cmd == "pack": sys.exit(0 if pack(sys.argv[2], int(sys.argv[3])) else 1)
    elif cmd == "all":
        ok = check(); timeline(); project()
        ok &= leak([os.path.join(OUT, "packets", f"ch{n:02d}_writer.md") for n in W["chapters"] if n < SOL])
        sys.exit(0 if ok else 1)
    else: print(__doc__)
