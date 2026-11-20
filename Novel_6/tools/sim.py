#!/usr/bin/env python3
"""sim.py — mx02 孤島の洋館：人物をエージェントとして動かし、真実台帳と知覚ログを作る

  python3 tools/sim.py run SEED            一回まわす → runs/seedNNNN/
  python3 tools/sim.py batch N [--top K]   N回まわして採点 → runs/SCOREBOARD.md、上位K回を runs/ に残す

v0 の方針
- 行動は規則ベース（性向・予定・恐怖・疑い）。のちに一部の人物を LLM に差し替えられるよう、
  decide() を人物ごとの「方針」として分けてある。
- 物理（位置・移動・鍵・明るさ・視線・音）はエンジンが強制する。誰も物理を破れない。
- 出力は「起きたこと」（真実台帳）と「誰が何を知覚したか」（知覚ログ）。語り手の選択と散文化は後段。
"""
import os, sys, random, argparse, html, itertools
from collections import defaultdict, deque
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TW = yaml.safe_load(open(os.path.join(ROOT, "twin", "MANSION.yaml"), encoding="utf-8"))
CA = yaml.safe_load(open(os.path.join(ROOT, "cast", "CAST.yaml"), encoding="utf-8"))
P = TW["places"]
TICK = TW["meta"]["tick"]

# ------------------------------------------------------------------ 時刻
def hm(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)

def dt(s):  # "2 07:30" -> 通しの分
    d, t = s.split(); return (int(d) - 1) * 1440 + hm(t)

def clock(t):
    d, m = divmod(t, 1440); return f"{d + 1}日目 {m // 60:02d}:{m % 60:02d}"

def hhmm(t):
    m = t % 1440; return f"{m // 60:02d}:{m % 60:02d}"

NS, NE = (hm(x) for x in TW["meta"]["night"])
def night(t):
    m = t % 1440; return m >= NS or m < NE

SCH = CA["schedule"]
T_ARRIVE, T_WILL, T_END = dt(SCH["arrive"]), dt(SCH["will"]), dt(SCH["boat"])

MEALS = {k: hm(v) for k, v in SCH["meals"].items()}
MEAL_LEN = SCH["meal_len"]

# ------------------------------------------------------------------ 地図
ADJ = defaultdict(set)
for a, b in TW["edges"]:
    ADJ[a].add(b); ADJ[b].add(a)
VIS = defaultdict(set)
for a, b in TW.get("visibility", []):
    VIS[a].add(b); VIS[b].add(a)
WALL = defaultdict(set)
for a, b in TW.get("walls", []):
    WALL[a].add(b); WALL[b].add(a)
UP, DOWN = defaultdict(set), defaultdict(set)   # UP[x]: xの上の部屋
for up, down in TW.get("floors", []):
    UP[down].add(up); DOWN[up].add(down)

def bfs(src):
    prev, q = {src: None}, deque([src])
    while q:
        x = q.popleft()
        for y in sorted(ADJ[x]):
            if y not in prev:
                prev[y] = x; q.append(y)
    return prev

PREV = {p: bfs(p) for p in P}
def next_hop(a, b):
    if a == b: return a
    pr = PREV[b]; x = a  # bから逆にたどる木で、aの親が次の一歩
    return pr[x]

DIST = {a: {} for a in P}
for a in P:
    for b in P:
        n, x = 0, a
        while x != b:
            x = next_hop(x, b); n += 1
        DIST[a][b] = n

def mirror(p): return P[p].get("mirror")
def spoken(p): return P[p]["spoken"]
def is_room(p): return P[p]["kind"] == "room"
def outdoor(p): return P[p]["kind"] == "outdoor"
def passage(p): return P[p]["kind"] == "passage"

# ------------------------------------------------------------------ 人物
class Agent:
    def __init__(s, aid, c, rng):
        s.id, s.name = aid, c["name"]
        s.room = c["room"]
        s.aggr, s.caution = c["aggression"], c["caution"]
        s.social, s.outdoor = c["social"], c["outdoor"]
        s.role, s.duty = c["role"], c.get("duty")
        s.items = set(c.get("items", []))
        s.loc = "hall"; s.believed = None      # believed: 取り違えているときの「思っている場所」
        s.alive, s.asleep = True, False
        s.goal, s.goal_until = None, 0
        s.susp = defaultdict(float)
        s.last_seen = {}                       # other -> (t, place, alone?)
        s.killer, s.target = False, None
        s.poison_due = None
        s.skip_meals = False
        s.night_hunt = {}
        s.bed = {d: hm(SCH["bed"][0]) + rng.randrange(0, hm(SCH["bed"][1]) - hm(SCH["bed"][0]) + 1, TICK) for d in range(1, 5)}
        s.rise = {d: hm(SCH["rise"][0]) + rng.randrange(0, hm(SCH["rise"][1]) - hm(SCH["rise"][0]) + 1, TICK) for d in range(1, 5)}
        s.stays = []                           # [place, believed, t0, t1]
        s.open_see = {}                        # (other, place) -> [t0, identified, asleep]
        s.perc = []

class World:
    def __init__(w, seed):
        w.seed, w.rng = seed, random.Random(seed)
        w.A = {aid: Agent(aid, c, w.rng) for aid, c in CA["characters"].items()}
        w.t = T_ARRIVE
        w.locked = {p: bool(P[p].get("locked_initially")) for p in P if P[p].get("lockable")}
        w.items = {}                           # item instance -> place or agent id
        for p, d in P.items():
            for it in d.get("items", []):
                w.items[f"{it}@{p}"] = ("place", p)
        for a in w.A.values():
            for it in list(a.items):
                w.items[f"{it}#{a.id}"] = ("agent", a.id)
            a.items = set()
        for k, (kind, where) in w.items.items():
            if kind == "agent": w.A[where].items.add(k)
        w.carafe = {}                          # room -> poisoner id（水差しの毒）
        w.cup = {}                             # 食事の杯に毒: victim -> poisoner
        w.corpses = {}                         # victim -> {place, t, found, sea}
        w.events, w.statements = [], []
        w.sounds = []                          # このtickの音 (kind, place, who)
        w.alarm = None                         # (place, until, reason)
        w.search = deque()
        w.fear = 0
        w.last_round = T_WILL
        w.deaths = []
        w.nev = 0
        w.pending_exam = None
        w.pending_round = None
        w.will_read = False

    # ---------------------------------------------------------- 記録
    def ev(w, kind, place, actors, **kw):
        w.nev += 1
        e = {"id": f"E{w.nev:03d}", "t": w.t, "clock": clock(w.t), "kind": kind, "place": place, "actors": list(actors)}
        e.update(kw); w.events.append(e); return e

    def perceive(w, a, kind, **kw):
        r = {"t": w.t, "clock": clock(w.t), "kind": kind, "place": a.loc}
        if a.believed: r["believed_place"] = a.believed
        r.update(kw); a.perc.append(r)

    def lit(w, p):
        if outdoor(p): return not night(w.t)
        if not P[p].get("dark_at_night"):
            return not night(w.t) or any(b.alive and not b.asleep and b.loc == p for b in w.A.values())
        return not night(w.t)

    def living(w): return [a for a in w.A.values() if a.alive]

    def at(w, p, awake=True):
        return [a for a in w.A.values() if a.alive and a.loc == p and (not awake or not a.asleep)]

    # ---------------------------------------------------------- 移動
    def move(w, a, goal):
        if a.loc == goal: return
        tgt = goal
        if a.believed and goal == a.room and mirror(goal):
            tgt = mirror(goal)                 # 取り違えたまま自分の部屋へ → 鏡の部屋に着く
        nx = next_hop(a.loc, tgt)
        if P[nx].get("lockable") and w.locked.get(nx) and nx != a.room:
            if not w.enter_locked(a, nx): return
        if nx == a.room and w.locked.get(nx):
            w.locked[nx] = False
        # 暗がりで回廊から棟の廊下へ入るとき、東西を取り違えることがある
        prev = a.loc
        if is_room(prev) and prev != a.room and w.locked.get(prev):
            w.locked[prev] = False               # 内側のつまみを回して出た。外からは鍵なしで掛けられない
        if prev == "gallery" and nx in ("w_cor", "e_cor") and night(w.t) and not a.believed and goal == a.room \
                and w.rng.random() < 0.08:
            a.loc = mirror(nx); a.believed = nx   # 自分の棟へ曲がったつもりで、反対の棟に入った
            w.ev("disoriented", a.loc, [a.id], believed=a.believed, note="暗い回廊で東西を取り違えた")
            return
        a.loc = nx
        if a.believed:
            if mirror(nx): a.believed = mirror(nx)
            else: w.reorient(a, f"{P[nx]['name']}に出た")
        if a.believed and is_room(nx) and nx != a.room:
            # 自分の部屋だと思って鏡の部屋に入った
            w.reorient(a, "部屋の中が違う（寝台の荷物・窓の外）")

    def reorient(w, a, why):
        w.ev("reoriented", a.loc, [a.id], why=why)
        w.perceive(a, "reoriented", why=why, was_believed=a.believed)
        a.believed = None

    def enter_locked(w, a, room):
        if room == "study":
            if any(i.startswith("master_key") for i in a.items) and a.killer:
                w.locked[room] = False
                w.ev("unlock", room, [a.id], how="合鍵"); w.sounds.append(("lock", room, a.id))
                return True
            return False
        owner = next((b for b in w.A.values() if b.room == room), None)
        if any(i.startswith("master_key") for i in a.items) and a.killer:
            w.locked[room] = False
            w.ev("unlock", room, [a.id], how="合鍵"); w.sounds.append(("lock", room, a.id))
            return True
        if a.believed:
            w.reorient(a, "鍵が合わない"); return False
        if a.killer and owner and owner.alive and owner.loc == room and not owner.asleep:
            w.sounds.append(("knock", room, a.id))
            w.ev("knock", room, [a.id, owner.id])
            if owner.susp[a.id] < 0.4 and w.rng.random() < 0.5:
                w.locked[room] = False
                w.ev("open_door", room, [owner.id, a.id])
                return True
        return False

    # ---------------------------------------------------------- 方針
    def meal_now(w):
        m = w.t % 1440
        for k, s in MEALS.items():
            if s <= m < s + MEAL_LEN: return k
        return None

    def decide(w, a):
        d = w.t // 1440 + 1; m = w.t % 1440
        caut = min(1.0, a.caution + 0.12 * w.fear)
        # 就寝・起床
        if a.asleep:
            if m == a.rise.get(d, 400) or (m > a.rise.get(d, 400) and m < 720):
                a.asleep = False
                w.perceive(a, "wake")
            return None
        # 集合（死体の発見・捜索）
        if w.alarm and w.t < w.alarm[1]:
            return w.alarm[0]
        nd = d if m >= 720 else d - 1          # 「その夜」
        hunting = a.killer and a.target and a.night_hunt.setdefault(nd, w.rng.random() < a.aggr)
        if hunting and (m >= a.bed.get(d, 1380) - 20 or m < 300) and w.rng.random() < 0.04:
            a.night_hunt[nd] = hunting = False  # 今夜はあきらめる
        if a.loc == a.room and (m >= a.bed.get(d, 1380) or m < 300) and not hunting:
            a.asleep = True
            w.flush(a)
            if a.room in w.locked and caut > 0.25: w.locked[a.room] = True
            if a.room in w.carafe:
                by = w.carafe.pop(a.room)
                a.poison_due = w.t + w.rng.randrange(30, 121, TICK)
                w.ev("drink_poison", a.room, [a.id], poisoner=by, note="寝る前に水差しの水を飲んだ")
            w.perceive(a, "sleep")
            return None
        # 職務
        if a.duty == "cook":
            for k, s in MEALS.items():
                if s - 45 <= m < s + MEAL_LEN: return "kitchen" if m < s else "dining"
            if m >= 1290 or m < 360: return a.room
            return "kitchen"
        meal = w.meal_now()
        if meal and not (a.skip_meals and caut > 0.6):
            return "dining"
        if m >= a.bed.get(d, 1380) - 20 or m < 300:
            if hunting: return w.hunt(a) or a.room
            return a.room
        if a.killer and a.target:
            g = w.hunt(a)
            if g: return g
        if w.t < a.goal_until and a.goal: return a.goal
        r = w.rng.random()
        if r < caut * 0.6:
            g = a.room
        elif r < caut * 0.6 + a.outdoor * 0.35 and not night(w.t):
            g = w.rng.choice(["garden", "garden", "cliff", "pier"])
        elif r < caut * 0.6 + a.outdoor * 0.35 + a.social * 0.5:
            g = w.rng.choice(["hall", "library", "billiard", "dining"])
        else:
            g = w.rng.choice([a.room, "library", "billiard", "hall", "garden" if not night(w.t) else "hall"])
        if a.duty == "butler" and w.rng.random() < 0.5: g = w.rng.choice(["hall", "dining", "kitchen"])
        a.goal, a.goal_until = g, w.t + w.rng.choice([15, 30, 45, 60, 90])
        return g

    def weapon(w, a):
        for k in ("revolver", "knife", "candlestick"):
            for i in a.items:
                if i.startswith(k): return i
        return None

    def hunt(w, a):
        v = w.A.get(a.target)
        if not v or not v.alive:
            a.target = None; return None
        # 毒を持っていて、相手の部屋が空いているなら水差しに
        if any(i.startswith("poison") for i in a.items) and v.loc != v.room and v.room not in w.carafe and w.rng.random() < 0.5:
            return v.room
        if not w.weapon(a) and not any(i.startswith("poison") for i in a.items):
            if any(i.startswith("master_key") for i in a.items) and w.items.get("revolver@study") == ("place", "study"): return "study"
            if any(w.items[i] == ("place", "kitchen") for i in w.items if i.startswith("knife")): return "kitchen"
            for p in ("billiard", "library"):
                if w.items.get(f"candlestick@{p}") == ("place", p): return p
        seen = a.last_seen.get(v.id)
        if seen and w.t - seen[0] <= 60: return seen[1]
        if night(w.t): return v.room
        return None

    # ---------------------------------------------------------- 犯行
    def act(w, a):
        if not a.alive or a.asleep: return
        others = [b for b in w.at(a.loc) if b.id != a.id]
        sleepers = [b for b in w.at(a.loc, awake=False) if b.asleep and b.id != a.id]
        watchers = list(others)
        if w.lit(a.loc):
            for q in VIS[a.loc]:
                if w.lit(q): watchers += w.at(q)
        # 凶器を拾う（誰も見ていないとき）
        if a.killer and not watchers:
            for i, (kind, where) in list(w.items.items()):
                if kind == "place" and where == a.loc and i.split("@")[0] in ("knife", "candlestick", "poison", "revolver") and w.rng.random() < 0.7:
                    w.items[i] = ("agent", a.id); a.items.add(i)
                    w.ev("take", a.loc, [a.id], item=i)
                    w.perceive(a, "act", what=f"{i.split('@')[0]}を手に取った")
                    break
        # 合鍵を盗む（執事が眠っているとき）
        if a.killer and a.loc == "srv_a":
            b = w.A["kashiwagi"]
            if b.alive and b.asleep and b.loc == "srv_a" and not watchers:
                for i in list(b.items):
                    if i.startswith("master_key") and w.rng.random() < 0.5:
                        b.items.discard(i); a.items.add(i); w.items[i] = ("agent", a.id)
                        w.ev("steal", "srv_a", [a.id, b.id], item=i)
                        w.perceive(a, "act", what="眠っている執事から合鍵を抜き取った")
        if not (a.killer and a.target): return
        v = w.A[a.target]
        # 水差しに毒（相手の部屋に一人でいるとき）
        if a.loc == v.room and v.loc != v.room and not others and a.loc not in w.carafe:
            pz = next((i for i in a.items if i.startswith("poison")), None)
            if pz:
                w.carafe[a.loc] = a.id
                w.ev("poison_carafe", a.loc, [a.id], victim=v.id, item=pz)
                w.perceive(a, "act", what=f"{v.name}の部屋の水差しに毒を入れた")
                return
        # 食事の杯に毒（皆がいる中でのすり替え。見られることがある）
        if a.loc == "dining" and v.loc == "dining" and w.meal_now() and v.id not in w.cup:
            pz = next((i for i in a.items if i.startswith("poison")), None)
            if pz and w.rng.random() < 0.15:
                w.cup[v.id] = a.id
                e = w.ev("poison_cup", "dining", [a.id], victim=v.id, item=pz)
                w.perceive(a, "act", what=f"{v.name}の杯に毒を落とした")
                for b in others:
                    if b.id != v.id and w.rng.random() < 0.15:
                        w.perceive(b, "see_act", subject=a.id, what=f"{a.name}が{v.name}の杯のあたりに手を伸ばした", identified=True)
                        e.setdefault("glimpsed_by", []).append(b.id)
                return
        # 直接手をくだす
        if v.loc != a.loc or not v.alive: return
        if [b for b in watchers if b.id != v.id]: return
        if [b for b in sleepers if b.id != v.id]: return
        if w.rng.random() > 0.7: return
        wp = w.weapon(a)
        if a.loc == "cliff" and not v.asleep:
            method = "push"
        elif wp:
            method = {"revolver": "shoot", "knife": "stab", "candlestick": "blunt"}[wp.split("@")[0]]
        elif v.asleep or a.aggr > 0.6:
            method = "strangle"
        else:
            return
        w.kill(a, v, method, wp)

    def kill(w, a, v, method, wp):
        lit = w.lit(a.loc) or (is_room(a.loc) and not v.asleep)
        saw = (not v.asleep) and lit
        e = w.ev("murder", a.loc, [a.id, v.id], killer=a.id, victim=v.id, method=method, weapon=wp,
                 victim_awake=not v.asleep, victim_saw_killer=saw)
        scream = {"stab": 0.5, "blunt": 0.25, "strangle": 0.15, "push": 0.7, "shoot": 0.0}[method]
        if not v.asleep and w.rng.random() < scream: w.sounds.append(("scream", a.loc, v.id))
        if method == "shoot": w.sounds.append(("gunshot", a.loc, a.id))
        if method in ("blunt", "strangle", "stab"): w.sounds.append(("thud", a.loc, v.id))
        if saw:
            w.perceive(v, "last", subject=a.id, what=f"{a.name}が{ {'push':'突き落とした','shoot':'撃った','stab':'刺した','blunt':'殴った','strangle':'首を絞めた'}[method] }", identified=True)
        elif not v.asleep:
            w.perceive(v, "last", subject=None, what="暗がりで誰かに襲われた", identified=False, true_subject=a.id)
        w.perceive(a, "act", what=f"{v.name}を{ {'push':'崖から突き落とした','shoot':'撃った','stab':'刺した','blunt':'殴った','strangle':'絞めた'}[method] }")
        w.die(v, a.id, method, e)
        if method == "push":
            w.corpses[v.id]["sea"] = True
        # 合鍵があれば、部屋に鍵をかけて去ることがある（密室）
        if is_room(a.loc) and any(i.startswith("master_key") for i in a.items) and w.rng.random() < 0.5:
            w.corpses[v.id]["lock_after"] = True
        a.target = None
        a.killer = w.rng.random() < a.aggr  # 一人殺して、続けるかどうか
        if a.killer: w.pick_target(a)

    def flush(w, a):
        for k, (t0, ident, sl, frm) in a.open_see.items():
            a.perc.append({"t": t0, "clock": clock(t0), "t1": w.t, "kind": "see" if ident else "silhouette",
                           "subject": k[0] if ident else None, "true_subject": k[0], "place": k[1], "from": frm})
        a.open_see = {}

    def die(w, v, by, method, e):
        w.flush(v)
        v.alive = False
        w.corpses[v.id] = {"place": v.loc, "t": w.t, "found": False, "sea": False, "event": e["id"]}
        w.deaths.append({"victim": v.id, "t": w.t, "place": v.loc, "by": by, "method": method, "event": e["id"]})
        for b in w.A.values():
            if b.target == v.id: b.target = None

    def poison_tick(w):
        for a in w.living():
            if a.poison_due and w.t >= a.poison_due:
                by = a.poison_by if hasattr(a, "poison_by") else None
                e = w.ev("poison_death", a.loc, [a.id], victim=a.id, killer=by, asleep=a.asleep)
                if not a.asleep: w.sounds.append(("thud", a.loc, a.id))
                w.perceive(a, "last", what="喉が焼け、息ができなくなった" if not a.asleep else "（眠ったまま）", identified=False)
                w.die(a, by, "poison", e)
        if w.meal_now() is None:
            pass

    # ---------------------------------------------------------- 知覚
    def sense(w):
        for a in w.living():
            if a.asleep:
                for kind, p, who in w.sounds:
                    if w.reach(kind, p, a.loc) and kind in ("scream", "gunshot") and w.rng.random() < 0.7:
                        a.asleep = False
                        w.perceive(a, "hear", sound=kind, source=w.direction(a.loc, p), true_source=p, true_who=who, woke=True)
                continue
            # 同じ場所・見える場所の人
            cur = {}
            lit = w.lit(a.loc)
            for b in w.A.values():
                if b.id == a.id or not b.alive: continue
                if b.loc == a.loc:
                    cur[(b.id, b.loc)] = lit
                elif lit and b.loc in VIS[a.loc] and w.lit(b.loc):
                    cur[(b.id, b.loc)] = True
            for k in list(a.open_see):
                if k not in cur:
                    t0, ident, sl, frm = a.open_see.pop(k)
                    a.perc.append({"t": t0, "clock": clock(t0), "t1": w.t, "kind": "see" if ident else "silhouette",
                                   "subject": k[0] if ident else None, "true_subject": k[0], "place": k[1],
                                   "from": frm, **({"subject_asleep": True} if sl else {})})
            for k, lt in cur.items():
                if k not in a.open_see:
                    ident = lt or w.rng.random() < 0.25
                    a.open_see[k] = [w.t, ident, w.A[k[0]].asleep, a.believed or a.loc]
                if a.open_see[k][1]:
                    alone = len([b for b in w.living() if b.loc == k[1]]) == 1
                    a.last_seen[k[0]] = (w.t, k[1], alone)
            # 死体
            for vid, c in w.corpses.items():
                if c["found"] or c["sea"] or c["place"] != a.loc: continue
                if any(d["victim"] == vid and d["by"] == a.id and w.t - d["t"] < 60 for d in w.deaths): continue  # 手を下した者はすぐには「見つけ」ない
                if lit or w.rng.random() < 0.4:
                    w.discover(a, vid)
            # 音
            for kind, p, who in w.sounds:
                if who == a.id or p == a.loc and kind in ("thud", "knock", "lock"): continue
                if w.reach(kind, p, a.loc):
                    w.perceive(a, "hear", sound=kind, source=w.direction(a.loc, p), true_source=p, true_who=who)
            # 窓の外（夜の灯台は西だけ）
            if is_room(a.loc) and night(w.t) and a.believed and P[a.loc]["wing"] == "W":
                w.reorient(a, "窓の外で灯台の灯が回っている")
        w.sounds = []

    def reach(w, kind, src, p):
        if kind == "gunshot": return not outdoor(p) or p == "garden" or outdoor(src)
        if kind == "scream": return p == src or p in WALL[src] or p in ADJ[src] or p in UP[src] or p in DOWN[src]
        if kind == "thud": return p == src or p in WALL[src] or p in UP[src] or p in DOWN[src]
        if kind in ("knock", "lock"): return p == src or p in ADJ[src]
        return False

    def direction(w, here, src):
        if here == src: return "ここ"
        if src in WALL[here]: return "隣の部屋"
        if src in UP[here]: return "上の階"
        if src in DOWN[here]: return "下の階"
        if src in ADJ[here]: return spoken(src)
        return "どこか遠く"

    def discover(w, a, vid):
        c = w.corpses[vid]; c["found"] = True; c["found_t"] = w.t; c["found_by"] = a.id
        v = w.A[vid]
        w.ev("discovery", c["place"], [a.id], victim=vid)
        w.perceive(a, "find", subject=vid, what=f"{v.name}が死んでいる")
        w.sounds.append(("scream", c["place"], a.id))
        w.fear += 1
        w.alarm = (c["place"], w.t + 45, f"discovery:{vid}")
        w.pending_round = w.t + 30
        doc = w.A["enami"]
        if doc.alive:
            lo = c["t"] - w.rng.choice([30, 45, 60]); hi = c["t"] + w.rng.choice([15, 30, 45])
            w.pending_exam = (vid, lo, hi)
        # 殺意の連鎖
        for b in w.living():
            if not b.killer and b.aggr >= 0.25 and w.rng.random() < b.aggr * 0.6:
                b.killer = True
                w.ev("resolve", b.loc, [b.id], note="先にやらなければ、と決めた")
            if b.killer and not b.target: w.pick_target(b)

    def pick_target(w, a):
        cands = [b for b in w.living() if b.id != a.id]
        if not cands: return
        best = max(cands, key=lambda b: a.susp[b.id] + w.rng.random() * 0.5)
        a.target = best.id

    # ---------------------------------------------------------- 集合と言明
    def gathering_round(w):
        place = w.alarm[0] if w.alarm else "dining"
        present = [a for a in w.at(place)]
        if hasattr(w, "pending_exam") and w.pending_exam and w.A["enami"] in present:
            vid, lo, hi = w.pending_exam
            e = w.ev("exam", place, ["enami"], victim=vid, window=[lo, hi], said=f"{hhmm(lo)}から{hhmm(hi)}のあいだ")
            for b in present:
                w.perceive(b, "told", speaker="enami", what=f"{w.A[vid].name}が死んだのは{hhmm(lo)}から{hhmm(hi)}のあいだ")
        w.pending_exam = None
        t0 = w.last_round
        for s in present:
            claims, hidden = w.claims(s, t0, w.t)
            st = {"id": f"S{len(w.statements) + 1:03d}", "t": w.t, "clock": clock(w.t), "place": place,
                  "speaker": s.id, "audience": [b.id for b in present if b.id != s.id], "claims": claims}
            if hidden: st["lie"] = True; st["hides"] = hidden
            # 目撃の申し立て：本物（名指しできた目撃）か、トリックスターの偽
            sight = w.sighting(s, t0)
            if sight: st["sighting"] = sight
            if s.role == "trickster" and w.rng.random() < 0.4:
                fake = w.fake_sighting(s, t0)
                if fake: st["sighting"] = fake; st["lie"] = True
            w.statements.append(st)
            for b in present:
                if b.id == s.id: continue
                w.perceive(b, "told", speaker=s.id, statement=st["id"])
                w.check_contradiction(b, s, st)
        w.last_round = w.t

    def claims(w, s, t0, t1):
        blocks = []
        for p, bel, a0, a1 in s.stays + ([[s.loc, s.believed, s._stay_t0, t1]] if s.alive else []):
            a0, a1 = max(a0, t0), min(a1, t1)
            if a1 - a0 < 10 or passage(p): continue
            if blocks and blocks[-1]["true_place"] == p:
                blocks[-1]["t1"] = a1; continue
            blocks.append({"place": spoken(bel or p), "true_place": p, "t0": a0, "t1": a1, "true": True,
                           **({"believed_place": bel} if bel else {})})
        hidden = []
        bad = [e for e in w.events if e["t"] >= t0 and s.id in e["actors"][:1] and e["kind"] in ("murder", "poison_carafe", "poison_cup", "take", "steal", "unlock")]
        def seen_by(b):
            n = 0
            for o in w.A.values():
                if o.id == s.id: continue
                if any(r["kind"] == "see" and r.get("subject") == s.id and r["place"] == b["true_place"]
                       and r["t"] < b["t1"] and r.get("t1", r["t"]) > b["t0"] for r in o.perc):
                    n += 1
            return n
        for e in bad:
            for b in blocks:
                if b["t0"] - 20 <= e["t"] <= b["t1"] + 20 and b["true_place"] != s.room and b["true"] and seen_by(b) < 2:
                    b["place"] = spoken(s.room); b["true"] = False; b["lie_cover"] = e["id"]
                    hidden.append(e["id"])
        if s.role == "trickster" and blocks and w.rng.random() < 0.3:
            b = w.rng.choice(blocks)
            if b["true"]:
                alt = w.rng.choice(["library", "billiard", "hall", s.room])
                if alt != b["true_place"]:
                    b["place"] = spoken(alt); b["true"] = False; b["lie_cover"] = "気まぐれ"
                    hidden.append("気まぐれ")
        for b in blocks:
            b["t0s"], b["t1s"] = hhmm(b["t0"] // 15 * 15), hhmm(-(-b["t1"] // 15) * 15)
        return blocks, sorted(set(hidden))

    def sighting(w, s, t0):
        # 死体が見つかった場所の近くで、名指しできた目撃があれば言う（本人が犯人でなければ）
        if not w.alarm: return None
        place = w.alarm[0]
        for r in reversed(s.perc):
            if r["kind"] == "see" and r.get("subject") and r["t"] >= t0 and r["place"] in ({place} | ADJ[place]) and r["subject"] != s.id:
                return {"subject": r["subject"], "place": spoken(r["place"]), "true_place": r["place"], "t": hhmm(r["t"]), "true": True}
        return None

    def fake_sighting(w, s, t0):
        cands = [b for b in w.living() if b.id != s.id]
        if not cands: return None
        b = w.rng.choice(cands)
        p = w.rng.choice(["cliff", "w_cor", "e_cor", "study", "kitchen", "garden"])
        tt = w.rng.randrange(t0, w.t + 1, TICK)
        truly = any(x[0] == p and x[2] <= tt <= x[3] for x in b.stays)
        return {"subject": b.id, "place": spoken(p), "true_place": p, "t": hhmm(tt), "true": truly, "fabricated": True}

    def check_contradiction(w, b, s, st):
        for c in st["claims"]:
            for r in b.perc:
                if r["kind"] == "see" and r.get("subject") == s.id and r["t"] < c["t1"] and r.get("t1", r["t"]) > c["t0"]:
                    if spoken(r["place"]) != c["place"]:
                        b.susp[s.id] += 0.4
                        w.perceive(b, "contradiction", subject=s.id, statement=st["id"],
                                   what=f"{w.A[s.id].name}は{c['place']}にいたと言うが、自分は{spoken(r['place'])}で見た")
                        return

    # ---------------------------------------------------------- 一刻み
    def step(w):
        if w.t >= T_WILL and not getattr(w, "will_read", False):
            w.will_read = True
            w.ev("will", "dining", [a.id for a in w.at("dining")], note="遺言の読み上げ。迎えの船まで島に残った者で等分")
            for a in w.living():
                w.perceive(a, "told", speaker="kuga", what="遺言：四日目の朝の船まで島に残った者で遺産を等分する")
                if a.aggr >= 0.6: a.killer = True; w.ev("resolve", a.loc, [a.id], note="遺言を聞いて決めた")
                if a.killer: w.pick_target(a)
        if w.t == dt("1 22:00"):
            w.ev("boat_lost", "pier", [], note="嵐で桟橋のボートが流された")
        w.poison_tick()
        # 毒の杯：食事の終わりに飲む
        if w.meal_now() is None and w.cup:
            for vid, by in list(w.cup.items()):
                v = w.A[vid]
                if v.alive:
                    v.poison_due = w.t + w.rng.randrange(20, 61, TICK); v.poison_by = by
                    w.ev("drink_poison", v.loc, [vid], poisoner=by, note="食事の杯を飲み干した")
            w.cup = {}
        for a in w.living():
            if a.poison_due and not hasattr(a, "poison_by"):
                ev = next((e for e in reversed(w.events) if e["kind"] == "drink_poison" and e["actors"][0] == a.id), None)
                a.poison_by = ev["poisoner"] if ev else None
        # 動く
        order = w.living(); w.rng.shuffle(order)
        for a in order:
            g = w.decide(a)
            if g and a.alive and not a.asleep:
                w.move(a, g)
        # 自分の部屋に戻ったら鍵
        for a in w.living():
            if a.loc == a.room and not a.asleep and a.room in w.locked and min(1, a.caution + 0.12 * w.fear) > 0.4:
                w.locked[a.room] = True
            elif a.loc != a.room and a.room in w.locked and not w.locked[a.room] and w.rng.random() < a.caution:
                if all(b.loc != a.room for b in w.living()): w.locked[a.room] = True
        # 手をくだす
        for a in order:
            w.act(a)
        for vid, c in w.corpses.items():
            if c.get("lock_after") and not c.get("locked_done"):
                w.locked[c["place"]] = True; c["locked_done"] = True
                w.ev("lock", c["place"], [w.deaths[-1]["by"]] if w.deaths else [], how="合鍵で外から")
        w.sense()
        # 集合のあとの言明
        if getattr(w, "pending_round", None) and w.t >= w.pending_round:
            w.pending_round = None
            w.gathering_round()
            w.alarm = None
        # 食事で欠けた者 → 捜索
        m = w.t % 1440
        if m in {s + MEAL_LEN - TICK for s in MEALS.values()} and w.t > T_WILL:
            present = {a.id for a in w.at("dining")}
            for a in w.A.values():
                if a.id in present: continue
                c = w.corpses.get(a.id)
                if a.alive and a.asleep: continue
                if c and not c["found"]:
                    w.search_for(a.id); break
        # 捜索：鍵のかかった部屋の前に着いたら、合鍵で開けるか扉を破る
        if w.alarm and str(w.alarm[2]).startswith("search") and w.locked.get(w.alarm[0]):
            p = w.alarm[0]
            here = [a for a in w.living() if not a.asleep and a.loc in ADJ[p]]
            if here:
                k = next((a for a in here if any(i.startswith("master_key") for i in a.items)), None)
                w.ev("search_unlock" if k else "break_door", p, [x.id for x in here], note="合鍵で開けた" if k else "合鍵が見当たらず、扉を破った")
                w.locked[p] = False
                for c in w.corpses.values():
                    if c["place"] == p and not c["found"]: c["behind_lock"] = True
                for b in here:
                    w.perceive(b, "act" if (k and b is k) else "see_act", what="合鍵で扉を開けた" if k else "皆で扉を破った",
                               subject=k.id if k else None, identified=True)
        # 滞在の記録
        for a in w.A.values():
            key = (a.loc, a.believed)
            if not hasattr(a, "_stay"):
                a._stay, a._stay_t0 = key, w.t
            elif a._stay is None:
                continue
            elif not a.alive:                  # この刻みに死んだ：死んだ場所に、この刻みのあいだはいた
                if a._stay != key:
                    a.stays.append([a._stay[0], a._stay[1], a._stay_t0, w.t]); a._stay_t0 = w.t
                a.stays.append([key[0], key[1], a._stay_t0, w.t + TICK])
                a._stay = None
            elif a._stay != key:
                a.stays.append([a._stay[0], a._stay[1], a._stay_t0, w.t])
                a._stay, a._stay_t0 = key, w.t
        w.t += TICK

    def search_for(w, vid):
        c = w.corpses[vid]
        if c["found"]: return
        if c["sea"]:
            if not c.get("missing"):
                c["missing"] = True
                ann = next((a for a in [w.A["kashiwagi"]] + w.living() if a.alive and a.loc == "dining"), None)
                w.ev("missing", "dining", [ann.id] if ann else [], victim=vid, note="姿が見えない。島じゅうを探したが見つからない")
                for b in w.at("dining"):
                    w.perceive(b, "told", speaker=ann.id if ann else None, what=f"{w.A[vid].name}がどこにもいない")
                w.fear += 1
            return
        w.alarm = (c["place"], w.t + 45, f"search:{vid}")

    def run(w):
        while w.t < T_END and len(w.living()) > 1:
            w.step()
        for a in w.A.values():
            if hasattr(a, "_stay") and a._stay:
                a.stays.append([a._stay[0], a._stay[1], a._stay_t0, w.t])
            w.flush(a)
            a.perc.sort(key=lambda r: r["t"])
        w.ev("end", "pier", [a.id for a in w.living()], note="迎えの船" if w.t >= T_END else "生き残りは一人")
        return w

# ------------------------------------------------------------------ 採点
def analyze(w):
    deaths = []
    for d in w.deaths:
        v = d["victim"]
        e = next(x for x in w.events if x["id"] == d["event"])
        killer = d["by"]
        # 犯行の前後15分に、犯人をその場所かその隣で名指しで見た者（被害者を除く）
        trace = set()
        for a in w.A.values():
            if a.id in (v, killer): continue
            for r in a.perc:
                if r["kind"] == "see" and r.get("subject") == killer and r["place"] in ({d["place"]} | ADJ[d["place"]]) \
                        and r["t"] - 15 <= d["t"] <= r.get("t1", r["t"]) + 15:
                    trace.add(a.id)
        heard = {a.id for a in w.A.values() if a.id not in (v, killer) for r in a.perc if r["kind"] == "hear" and r.get("true_who") in (v, killer) and abs(r["t"] - d["t"]) <= 5}
        c = w.corpses[v]
        deaths.append({**d, "victim_saw_killer": e.get("victim_saw_killer", False), "trace": sorted(trace), "heard": sorted(heard),
                       "found_t": c.get("found_t"), "found_by": c.get("found_by"), "sea": c["sea"], "locked_room": bool(c.get("lock_after") or c.get("behind_lock")),
                       "delayed": d["method"] == "poison"})
    lies = [s for s in w.statements if s.get("lie")]
    contra = sum(1 for a in w.A.values() for r in a.perc if r["kind"] == "contradiction")
    disor = sum(1 for e in w.events if e["kind"] == "disoriented")
    silh = sum(1 for a in w.A.values() for r in a.perc if r["kind"] == "silhouette" and night(r["t"]))
    killers = {d["by"] for d in w.deaths if d["by"]}
    surv = [a.id for a in w.living()]
    K = len(deaths)
    s = 0.0
    if not surv or K < 3: s = -99
    else:
        s += {1: 3, 2: 3, 3: 1}.get(len(surv), 0)
        s += 3 if 4 <= K <= 7 else (1 if K in (3, 8) else 0)
        s += 2 if len(killers) >= 3 else (1 if len(killers) == 2 else 0)
        s += sum(1 for d in deaths if not d["trace"]) * 0.7          # 誰にも見られていない犯行
        s += min(2, sum(1 for d in deaths if d["delayed"]))         # 遅れて死ぬ毒
        s += min(2, sum(1 for d in deaths if d["locked_room"]))     # 密室
        s += min(1, sum(1 for d in deaths if d["sea"]))             # 消えた死体
        s += sum(1 for d in deaths if d["by"] in {x["victim"] for x in deaths}) * 0.7  # 犯人が被害者に
        s += min(3, disor * 1.0)                                    # 東西の取り違え
        s += min(2, contra * 0.5)                                   # 矛盾として気づける嘘（手がかり）
        s += min(2, len(lies) * 0.3)
        # 解ける見込み：各殺人に、被害者の目か誰かの目撃・物音の手がかりがある
        solv = sum(1 for d in deaths if d["victim_saw_killer"] or d["trace"] or d["heard"]) / K
        s += 3 * solv
        s -= sum(1 for d in deaths if not (d["victim_saw_killer"] or d["trace"] or d["heard"] or d["delayed"])) * 0.8
    return {"seed": w.seed, "score": round(s, 2), "kills": K, "survivors": surv, "killers": sorted(killers),
            "deaths": deaths, "lies": len(lies), "contradictions": contra, "disoriented": disor, "dark_silhouettes": silh}

# ------------------------------------------------------------------ 物理の検査
def where(w, aid, t):
    for p, b, t0, t1 in w.A[aid].stays:
        if t0 <= t < t1: return p
    return None

def check(w):
    bad = []
    for a in w.A.values():
        st = a.stays
        for x, y in zip(st, st[1:]):
            if x[3] != y[2]: bad.append(f"{a.name}：滞在に切れ目 {clock(x[3])}→{clock(y[2])}")
            if x[0] != y[0] and y[0] not in ADJ[x[0]]: bad.append(f"{a.name}：{P[x[0]]['name']}から{P[y[0]]['name']}へ瞬間移動 {clock(y[2])}")
    for e in w.events:
        if e["kind"] == "murder":
            k, v = e["killer"], e["victim"]
            if where(w, k, e["t"]) != e["place"] or where(w, v, e["t"]) != e["place"]:
                bad.append(f"{e['id']} 殺人：二人が同じ場所にいない")
        if e["kind"] in ("poison_carafe", "discovery", "take", "steal"):
            if where(w, e["actors"][0], e["t"]) != e["place"]:
                bad.append(f"{e['id']} {e['kind']}：本人がその場所にいない")
    for a in w.A.values():
        for r in a.perc:
            if r["kind"] == "see" and r.get("subject"):
                ok = any(p == r["place"] and t0 < r.get("t1", r["t"] + 1) and t1 > r["t"] for p, b, t0, t1 in w.A[r["subject"]].stays)
                if not ok: bad.append(f"{a.name}の知覚：{w.A[r['subject']].name}を{P[r['place']]['name']}で見たが、そこにいない {r['clock']}")
    for s in w.statements:
        for c in s["claims"]:
            if c["true"]:
                ok = any(p == c["true_place"] and t0 < c["t1"] and t1 > c["t0"] for p, b, t0, t1 in w.A[s["speaker"]].stays)
                if not ok: bad.append(f"{s['id']}：真とした申し立てが滞在と合わない")
            elif "lie_cover" not in c:
                bad.append(f"{s['id']}：偽の申し立てに理由がない")
    return bad

# ------------------------------------------------------------------ 出力
METHOD = {"push": "崖から突き落とす", "shoot": "銃", "stab": "刃物", "blunt": "燭台で殴打", "strangle": "絞殺", "poison": "毒"}

def name(w, i): return w.A[i].name if i in w.A else (i or "—")

def write_run(w, an, outdir):
    os.makedirs(os.path.join(outdir, "truth"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "out"), exist_ok=True)
    stays = {a.id: [{"place": p, **({"believed": b} if b else {}), "from": clock(t0), "to": clock(t1)} for p, b, t0, t1 in a.stays] for a in w.A.values()}
    ledger = {"meta": {"seed": w.seed, "score": an["score"], "twin": "twin/MANSION.yaml", "cast": "cast/CAST.yaml",
                       "survivors": an["survivors"], "generated_by": "tools/sim.py v0"},
              "deaths": an["deaths"], "events": w.events, "statements": w.statements, "stays": stays}
    yaml.safe_dump(ledger, open(os.path.join(outdir, "truth", "LEDGER.yaml"), "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
    perc = {a.id: a.perc for a in w.A.values()}
    yaml.safe_dump(perc, open(os.path.join(outdir, "truth", "PERCEPTIONS.yaml"), "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
    write_summary(w, an, os.path.join(outdir, "out", "SUMMARY.md"))
    write_timeline(w, an, os.path.join(outdir, "out", "TIMELINE.html"))

def write_summary(w, an, path):
    L = [f"# seed {w.seed} — 得点 {an['score']}", "",
         f"- 死者 {an['kills']}人／生存 {len(an['survivors'])}人（{'、'.join(name(w, x) for x in an['survivors'])}）",
         f"- 手を下した者 {len(an['killers'])}人（{'、'.join(name(w, x) for x in an['killers'])}）",
         f"- 嘘の言明 {an['lies']}／矛盾として気づかれた嘘 {an['contradictions']}／東西の取り違え {an['disoriented']}／暗がりの人影 {an['dark_silhouettes']}", "",
         "## 死", "", "| 時刻 | 被害者 | 場所 | 手を下した者 | 方法 | 被害者は見た | 犯人を見た者 | 物音を聞いた者 | 発見 | 備考 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in an["deaths"]:
        note = []
        if d["locked_room"]: note.append("密室")
        if d["sea"]: note.append("死体は海へ")
        if d["delayed"]: note.append("遅れて死ぬ")
        found = f"{clock(d['found_t'])} {name(w, d['found_by'])}" if d.get("found_t") else ("行方不明" if d["sea"] else "未発見")
        L.append(f"| {clock(d['t'])} | {name(w, d['victim'])} | {P[d['place']]['name']}（{spoken(d['place'])}） | {name(w, d['by'])} | {METHOD[d['method']]} | "
                 f"{'○' if d['victim_saw_killer'] else '—'} | {'、'.join(name(w, x) for x in d['trace']) or '—'} | {'、'.join(name(w, x) for x in d['heard']) or '—'} | {found} | {'・'.join(note)} |")
    L += ["", "## 嘘", ""]
    for s in w.statements:
        if not s.get("lie"): continue
        bad = [c for c in s["claims"] if not c["true"]]
        txt = "／".join(f"{c['t0s']}〜{c['t1s']}は{c['place']}（本当は{P[c['true_place']]['name']}）" for c in bad)
        sg = s.get("sighting")
        if sg and sg.get("fabricated"): txt += f"／{name(w, sg['subject'])}を{sg['t']}に{sg['place']}で見た（{'偶然に本当' if sg['true'] else '作り話'}）"
        L.append(f"- {s['clock']} {name(w, s['speaker'])}：{txt}")
    L += ["", "## 東西の取り違え・名前の同じ場所", ""]
    for e in w.events:
        if e["kind"] in ("disoriented", "reoriented"):
            L.append(f"- {e['clock']} {name(w, e['actors'][0])}：{e['kind']} {P[e['place']]['name']} {e.get('believed', '') and '（' + P[e['believed']]['name'] + 'だと思った）'}{e.get('why', '')}")
    amb = [s for s in w.statements for c in s["claims"] if c["place"] in ("一号室", "二号室", "三号室", "四号室", "二階の廊下", "裏階段")]
    L.append(f"- 言明のうち、東西どちらか曖昧な場所を含むもの：{len(amb)}件")
    L += ["", "## 出来事（抜粋）", ""]
    for e in w.events:
        if e["kind"] in ("will", "resolve", "take", "steal", "unlock", "lock", "break_door", "knock", "open_door", "poison_carafe", "poison_cup",
                         "drink_poison", "murder", "poison_death", "discovery", "exam", "missing", "boat_lost", "end", "search_unlock", "disoriented"):
            who = "、".join(name(w, x) for x in e["actors"])
            extra = e.get("note") or e.get("method") or e.get("item") or e.get("said") or e.get("how") or ""
            L.append(f"- {e['clock']} [{e['kind']}] {P[e['place']]['name']}：{who} {extra}")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")

def write_timeline(w, an, path):
    COL = {"W": "#8fb3e0", "E": "#e0b08f", "C": "#c9c9c9", "O": "#9fd39a"}
    t0, t1 = T_ARRIVE, w.t
    step = 15
    cols = list(range(t0, t1, step))
    rows = []
    for a in w.A.values():
        cells = []
        sleeps, s0 = [], None
        for r in a.perc:
            if r["kind"] == "sleep": s0 = r["t"]
            elif r["kind"] in ("wake",) or (r["kind"] == "hear" and r.get("woke")):
                if s0 is not None: sleeps.append((s0, r["t"])); s0 = None
        if s0 is not None: sleeps.append((s0, w.t))
        for c in cols:
            st = next((x for x in a.stays if x[2] <= c < x[3]), None)
            dead = not a.alive and any(d["victim"] == a.id and d["t"] <= c for d in w.deaths)
            if dead:
                cells.append('<td class="dead"></td>'); continue
            if not st:
                cells.append("<td></td>"); continue
            p, bel = st[0], st[1]
            col = COL[P[p]["wing"]]
            mark = ""
            k = next((d for d in w.deaths if d["by"] == a.id and c <= d["t"] < c + step), None)
            if k: mark = "✕"
            cls = ("bel " if bel else "") + ("zz" if any(s0 <= c < s1 for s0, s1 in sleeps) else "")
            title = html.escape(f"{clock(c)} {P[p]['name']}" + (f"（{P[bel]['name']}だと思っている）" if bel else ""))
            cells.append(f'<td class="{cls}" style="background:{col}" title="{title}">{mark}</td>')
        rows.append(f"<tr><th>{html.escape(a.name)}</th>{''.join(cells)}</tr>")
    head = "".join(f"<th class='h'>{hhmm(c) if c % 120 == 0 else ''}</th>" for c in cols)
    days = "".join(f"<th class='h' colspan='1'>{(c // 1440) + 1}日</th>" if c % 1440 == 0 else "<th class='h'></th>" for c in cols)
    doc = f"""<!DOCTYPE html><html lang="ja"><meta charset="utf-8"><title>seed {w.seed} タイムライン</title>
<style>body{{font:12px sans-serif}}table{{border-collapse:collapse}}td{{width:7px;height:18px;padding:0;border-right:1px solid #fff;font-size:10px;color:#b00;text-align:center}}
th{{text-align:right;padding-right:6px;white-space:nowrap}}th.h{{font-weight:normal;font-size:9px;text-align:left}}td.dead{{background:#333}}td.bel{{outline:2px dashed #c00;outline-offset:-2px}}td.zz{{opacity:.45}}
.lg span{{display:inline-block;padding:2px 6px;margin-right:6px}}</style>
<h1>seed {w.seed}（得点 {an['score']}）</h1>
<p class="lg"><span style="background:{COL['W']}">西棟</span><span style="background:{COL['E']}">東棟</span><span style="background:{COL['C']}">中央</span><span style="background:{COL['O']}">屋外</span><span style="background:#333;color:#fff">死</span>✕＝手を下した　赤い破線＝東西を取り違えている　15分刻み</p>
<table><tr><th></th>{days}</tr><tr><th></th>{head}</tr>{''.join(rows)}</table></html>"""
    open(path, "w", encoding="utf-8").write(doc)

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "batch"])
    ap.add_argument("n", type=int)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(ROOT, "runs"))
    a = ap.parse_args()
    if a.cmd == "run":
        w = World(a.n).run(); an = analyze(w)
        write_run(w, an, os.path.join(a.out, f"seed{a.n:04d}"))
        print(an["score"], an["kills"], an["survivors"])
        return
    res, viol = [], 0
    for seed in range(1, a.n + 1):
        w = World(seed).run(); an = analyze(w); res.append(an)
        v = check(w); an["violations"] = len(v); viol += len(v)
        if v and viol <= len(v): print(f"seed {seed} の物理違反:", *v[:10], sep="\n  ")
    res.sort(key=lambda r: -r["score"])
    os.makedirs(a.out, exist_ok=True)
    L = [f"# スコアボード（{a.n}回）", "", "| 順位 | seed | 得点 | 死者 | 生存 | 手を下した者 | 嘘 | 矛盾 | 取り違え | 密室 | 毒 | 海 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(res[:30], 1):
        L.append(f"| {i} | {r['seed']} | {r['score']} | {r['kills']} | {len(r['survivors'])} | {len(r['killers'])} | {r['lies']} | {r['contradictions']} | {r['disoriented']} | "
                 f"{sum(d['locked_room'] for d in r['deaths'])} | {sum(d['delayed'] for d in r['deaths'])} | {sum(d['sea'] for d in r['deaths'])} |")
    valid = [r for r in res if r["score"] > -99]
    L += ["", f"- 物理の検査（瞬間移動・同時に二か所・見えないものを見た・裏づけのない申し立て）：違反 {viol}件",
          f"- 成立（生存者あり・死者3人以上）：{len(valid)}／{a.n}",
          f"- 死者の分布：{dict(sorted(__import__('collections').Counter(r['kills'] for r in res).items()))}",
          f"- 生存者の分布：{dict(sorted(__import__('collections').Counter(len(r['survivors']) for r in res).items()))}"]
    open(os.path.join(a.out, "SCOREBOARD.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    for r in res[:a.top]:
        w = World(r["seed"]).run(); an = analyze(w)
        write_run(w, an, os.path.join(a.out, f"seed{r['seed']:04d}"))
    print("\n".join(L))

if __name__ == "__main__":
    main()
