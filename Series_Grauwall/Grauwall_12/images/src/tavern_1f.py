exec(open('/home/claude/tavern/common.py').read())
# ---------- building (x: 0..14 west->east, y: 0..10 south(street)->north)
W, D, HW, HF = 14.0, 10.0, 2.7, 1.05   # full wall height, front cut height
T = 0.4
box("ground", (W/2, D/2, -0.06), (40, 40, 0.1), M_GROUND)
box("floor", (W/2, D/2, 0.0), (W, D, 0.04), M_FLOOR)
# back (north) and west walls: full height
box("wall_n", (W/2, D+T/2, HW/2), (W+2*T, T, HW), M_STONE)
box("wall_w", (-T/2, D/2, HW/2), (T, D, HW), M_STONE)
# front (south) and east walls: cut low (cutaway)
box("wall_s_a", (1.9, -T/2, HF/2), (3.8+T, T, HF), M_STONE)
box("wall_s_b", (9.9, -T/2, HF/2), (8.2+T, T, HF), M_STONE)
box("wall_e", (W+T/2, D/2, HF/2), (T, D+2*T, HF), M_STONE)
# front double doors (open, oak) and frame posts
for x in (3.8, 5.8): box("doorpost", (x, -T/2, 1.2), (0.18, T+0.08, 2.4), M_DARK)
box("door_l", (4.05, 0.35, 1.0), (0.08, 0.95, 2.0), M_WOOD, rot=(0,0,0))
box("door_r", (5.55, 0.35, 1.0), (0.08, 0.95, 2.0), M_WOOD)
box("lintel", (4.8, -T/2, 2.35), (2.2, T+0.1, 0.18), M_DARK)
# plaster upper band on full walls & dark beams on top
box("beam_n", (W/2, D+0.02, HW-0.1), (W, 0.25, 0.2), M_DARK)
box("beam_w", (0.02, D/2, HW-0.1), (0.25, D, 0.2), M_DARK)
for x in (3.5, 7.0, 10.5): box("post_n", (x, D-0.08, HW/2), (0.22, 0.2, HW), M_DARK)

# ---------- counter (east-west), egg jar at the west end near the stairs
CX0, CX1, CY = 3.0, 11.2, 7.2
box("counter_body", ((CX0+CX1)/2, CY, 0.55), (CX1-CX0, 0.55, 1.1), M_WOOD)
box("counter_top", ((CX0+CX1)/2, CY-0.03, 1.13), (CX1-CX0+0.15, 0.75, 0.07), M_DARK)
for i in range(7):
    x = CX0+0.8+i*1.1; cyl("stool", (x, CY-0.85, 0.35), 0.18, 0.7, M_DARK, verts=16); cyl("stoolseat", (x, CY-0.85, 0.72), 0.2, 0.05, M_WOOD, verts=20)
# egg jar (glass + brine + eggs)
jx, jy = CX0+0.35, CY-0.05
cyl("jar", (jx, jy, 1.36), 0.16, 0.42, M_GLASS)
cyl("brine", (jx, jy, 1.31), 0.145, 0.3, M_BRINE)
cyl("jarlid", (jx, jy, 1.59), 0.17, 0.04, M_WOOD)
sphere("bottom", (jx+0.02, jy, 1.18), 0.033, plain("redstone", (0.38,0.05,0.04), 0.8))
for k in range(12):
    a = k*2.4; rr = 0.08 if k % 2 else 0.04
    sphere("egg", (jx+math.cos(a)*rr, jy+math.sin(a)*rr, 1.24+0.03*k), 0.035, M_EGG)
# back bar: barrels on rack, shelves, blackboard, pillar with three nails
box("rack", (8.8, D-0.55, 0.35), (3.6, 0.8, 0.7), M_DARK)
for i in range(4):
    cyl("barrel", (7.4+i*0.95, D-0.55, 1.05), 0.38, 0.7, M_WOOD, rot=(math.pi/2,0,0))
    for dy in (-0.25, 0.25): cyl("hoop", (7.4+i*0.95, D-0.55+dy, 1.05), 0.395, 0.04, M_IRON, rot=(math.pi/2,0,0))
box("shelf1", (4.6, D-0.18, 1.5), (2.4, 0.3, 0.05), M_DARK); box("shelf2", (4.6, D-0.18, 1.95), (2.4, 0.3, 0.05), M_DARK)
for i in range(10):
    cyl("bottle", (3.6+i*0.22, D-0.18, 1.66 if i<6 else 2.11), 0.05, 0.28, plain(f"btl{i}", random.choice([(0.05,0.15,0.05),(0.25,0.12,0.03),(0.08,0.06,0.1)]), 0.1), verts=12)
box("blackboard", (5.9, D-0.03, 1.75), (1.1, 0.04, 0.8), M_BOARD)
for r in range(4): box("chalk", (5.75, D-0.06, 2.0-r*0.15), (0.6-0.1*(r%2), 0.01, 0.02), M_CHALK)
px = 7.0
box("pillar", (px, D-0.3, HW/2), (0.3, 0.3, HW), M_DARK)
for i, a in enumerate((-0.5, 0.0, 0.5)):
    cyl("nail", (px, D-0.47, 1.75), 0.018, 0.5, M_RUST, rot=(0, a, 0), verts=8)
    cyl("nailhead", (px+math.sin(a)*0.25, D-0.47, 1.75+math.cos(a)*0.25), 0.04, 0.02, M_RUST, rot=(0, a, 0), verts=12)
# apron on a hook
box("apron", (px+0.16, D-0.48, 1.25), (0.02, 0.35, 0.55), M_CLOTH)
# reception desk near the door
box("desk", (7.2, 1.2, 0.5), (1.4, 0.6, 1.0), M_WOOD); box("desktop", (7.2, 1.2, 1.02), (1.5, 0.7, 0.05), M_DARK)
box("ledger", (7.0, 1.2, 1.06), (0.35, 0.25, 0.04), M_CLOTH)

# ---------- fireplace on the east wall (cut wall, so the hearth stands as a stone block)
box("hearth", (W-0.45, 4.2, 0.95), (0.9, 2.0, 1.9), M_STONE)
box("hearth_open", (W-0.62, 4.2, 0.45), (0.6, 1.1, 0.8), plain("soot", (0.02,0.02,0.02), 0.95))
box("mantle", (W-0.7, 4.2, 1.15), (0.5, 2.2, 0.12), M_DARK)
for i in range(3): cyl("log", (W-0.65, 3.9+i*0.3, 0.15), 0.08, 0.6, M_DARK, rot=(0, math.pi/2, 0.2))
sphere("flame", (W-0.65, 4.2, 0.35), 0.18, M_FIRE)
plight((W-1.0, 4.2, 0.5), 900, (1.0,0.5,0.18), 0.3)

# ---------- six tables with benches
for i, (tx, ty) in enumerate([(2.2,2.0),(5.0,4.4),(9.6,2.2),(2.3,4.9),(9.4,4.8),(11.9,2.4)]):
    rot = random.uniform(-0.12, 0.12)
    box("table", (tx, ty, 0.74), (1.6, 0.9, 0.08), M_WOOD, rot=(0,0,rot))
    for dx in (-0.65,0.65):
        for dy in (-0.33,0.33):
            box("leg", (tx+dx, ty+dy, 0.36), (0.08,0.08,0.72), M_DARK)
    box("bench", (tx, ty-0.75, 0.42), (1.5, 0.32, 0.06), M_WOOD, rot=(0,0,rot)); box("bench", (tx, ty+0.75, 0.42), (1.5, 0.32, 0.06), M_WOOD, rot=(0,0,rot))
    for dx in (-0.6,0.6):
        for dy in (-0.75,0.75): box("bl", (tx+dx, ty+dy, 0.2), (0.06,0.28,0.4), M_DARK)
    # mug(s) and a small lamp
    for k in range(random.randint(1,3)):
        cyl("mug", (tx-0.4+k*0.35, ty+random.uniform(-0.2,0.2), 0.86), 0.06, 0.16, M_WOOD, verts=16)
    cyl("lampbase", (tx+0.45, ty, 0.82), 0.05, 0.08, M_IRON, verts=12); sphere("lampflame", (tx+0.45, ty, 0.9), 0.03, M_LAMP)
    plight((tx+0.45, ty, 1.0), 25, (1.0,0.68,0.35), 0.05)
# soup pot on the counter end near the kitchen
cyl("pot", (CX1-0.6, CY, 1.3), 0.2, 0.28, M_IRON); cyl("soup", (CX1-0.6, CY, 1.43), 0.18, 0.02, M_SOUP)

# ---------- long bench in the corner (where the northern woman slept)
box("longbench", (0.45, 0.9, 0.42), (0.6, 1.9, 0.08), M_WOOD); box("lb_back", (0.18, 0.9, 0.75), (0.08, 1.9, 0.6), M_WOOD)
box("blanket", (0.5, 0.75, 0.5), (0.5, 1.0, 0.07), M_BLANKET)

# ---------- stairs along the west wall going north, open storage under them
s_y0, s_y1, n = 4.4, 9.4, 12
for i in range(n):
    y = s_y0 + (s_y1-s_y0)*(i+0.5)/n; z = (i+1)*HW/n
    box("step", (0.75, y, z-0.04), (1.1, (s_y1-s_y0)/n+0.02, 0.08), M_WOOD)
box("stringer", (1.32, (s_y0+s_y1)/2, HW/2-0.1), (0.08, s_y1-s_y0, 0.12), M_DARK, rot=(math.atan2(HW, s_y1-s_y0),0,0))
box("bookbox", (0.6, 8.6, 0.25), (0.8, 0.6, 0.5), M_WOOD)
box("goboard", (0.6, 8.6, 0.53), (0.42, 0.42, 0.04), plain("goboard", (0.55,0.42,0.22), 0.6))
for k in range(9):
    sphere("stone", (0.45+random.random()*0.3, 8.45+random.random()*0.3, 0.56), 0.018, plain(f"st{k}", (0.9,0.9,0.85) if k%2 else (0.04,0.04,0.04), 0.3))
cyl("broom", (0.25, 7.6, 0.75), 0.02, 1.5, M_WOOD, rot=(0.15,0,0), verts=8)
box("broomhead", (0.25, 7.5, 0.08), (0.2, 0.25, 0.16), plain("straw", (0.55,0.45,0.2), 0.95))

# ---------- back door (north wall, east end) with a glimpse of the soup table outside
box("backdoor", (12.6, D+0.02, 1.0), (0.95, T+0.06, 2.0), M_DARK)
box("bar", (12.6, D-0.22, 1.05), (1.1, 0.08, 0.1), M_WOOD)

# ---------- alley behind the back door, with the soup table
box("alley", (W/2+2, D+T+0.8, 0.0), (W+8, 1.6, 0.04), plain("cobble", (0.2,0.19,0.18), 0.9))
box("gutter", (W/2+2, D+T+1.45, 0.01), (W+8, 0.18, 0.03), plain("gutter", (0.03,0.04,0.05), 0.2))
box("neighbor", (W/2, D+T+1.85, HF/2), (W+2, 0.4, HF), M_STONE)
box("souptable", (12.6, D+T+0.45, 0.45), (1.0, 0.45, 0.06), M_WOOD)
for dx in (-0.4,0.4): box("stleg", (12.6+dx, D+T+0.45, 0.22), (0.06,0.06,0.44), M_DARK)
for dx in (-0.2,0.2): cyl("bowl", (12.6+dx, D+T+0.45, 0.51), 0.09, 0.06, M_WOOD, verts=16)
plight((12.6, D+T+0.6, 1.6), 60, (1.0,0.7,0.4), 0.1)
# ---------- courtyard to the east: well and stable
CXo = W+T
box("yard", (CXo+3.0, 6.5, 0.0), (6.0, 7.0, 0.04), plain("yardsoil", (0.16,0.13,0.10), 0.95))
box("yardwall_s", (CXo+3.0, 3.0, HF/2), (6.0, 0.35, HF), M_STONE)
box("yardwall_e", (CXo+6.0, 6.5, HF/2), (0.35, 7.0, HF), M_STONE)
cyl("well", (CXo+1.8, 5.0, 0.4), 0.55, 0.8, M_STONE); cyl("wellwater", (CXo+1.8, 5.0, 0.62), 0.42, 0.02, plain("water", (0.02,0.03,0.05), 0.05))
for dx in (-0.5,0.5): box("wellpost", (CXo+1.8+dx, 5.0, 1.15), (0.1,0.1,1.5), M_DARK)
box("wellbeam", (CXo+1.8, 5.0, 1.9), (1.2,0.12,0.12), M_DARK); cyl("bucket", (CXo+1.8, 5.0, 1.35), 0.14, 0.22, M_WOOD, verts=16)
# stable: open-fronted shed with a loft
box("stable_floor", (CXo+3.8, 8.6, 0.05), (4.0, 2.6, 0.06), plain("straw2", (0.5,0.4,0.18), 0.95))
box("stable_back", (CXo+3.8, 9.9, 1.3), (4.0, 0.15, 2.6), M_WOOD)
box("stable_side", (CXo+5.8, 8.6, 1.3), (0.15, 2.6, 2.6), M_WOOD)
for x in (CXo+1.9, CXo+3.8): box("stable_post", (x, 7.4, 1.3), (0.15,0.15,2.6), M_DARK)
box("loft", (CXo+3.8, 8.9, 1.6), (4.0, 2.1, 0.08), M_WOOD)
for k in range(5): box("hay", (CXo+2.4+k*0.7, 9.3, 1.75), (0.6, 0.9, 0.25), plain(f"hay{k}", (0.42,0.33,0.15), 0.95))
plight((CXo+2.5, 6.5, 2.4), 80, (1.0,0.7,0.4), 0.1)

# ---------- hanging lamps over the hall
for (x, y) in [(4.0,3.2),(8.0,3.4),(11.0,5.6)]:
    cyl("chain", (x, y, 2.45), 0.01, 0.5, M_IRON, verts=6); sphere("hanglamp", (x, y, 2.15), 0.07, M_LAMP)
    plight((x, y, 2.05), 220, (1.0,0.7,0.4), 0.1)
plight((6.5, 8.6, 2.2), 160, (1.0,0.72,0.42), 0.1)   # behind the counter

# ---------- world: dim blue night
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True
bg = wd.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.012,0.016,0.03,1); bg.inputs["Strength"].default_value = 1.0
bpy.ops.object.light_add(type='AREA', location=(7, 4, 12)); A = bpy.context.object; A.data.energy = 2200; A.data.size = 16; A.data.color = (0.62,0.7,0.95)

# ---------- camera: high three-quarter view from the street side (south-east)
bpy.ops.object.camera_add(location=(21.5, -9.0, 15.5)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 33
tgt = Vector((9.8, 5.6, 0.4)); d = tgt - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = OUT
import json
from bpy_extras.object_utils import world_to_camera_view
anchors = {"front":(4.8,-0.3,1.0),"desk":(7.2,1.2,1.1),"counter":(8.0,CY,1.2),"jar":(jx,jy,1.6),"nails":(px,D-0.45,2.0),"barrels":(8.8,D-0.55,1.5),
  "board":(5.9,D-0.05,2.2),"hearth":(W-0.45,4.2,1.9),"tables":(5.0,4.4,0.8),"stairs":(0.75,7.5,2.0),"storage":(0.6,8.6,0.6),"bench":(0.45,0.9,0.8),
  "backdoor":(12.6,D,2.0),"soup":(12.6,D+T+0.45,0.6),"well":(CXo+1.8,5.0,1.9),"stable":(CXo+3.8,8.9,2.6)}
out={}
for k,v in anchors.items():
    co = world_to_camera_view(sc, cam, Vector(v)); out[k]=[co.x, 1-co.y]
json.dump(out, open(OUT.rsplit('.',1)[0]+'_anchors.json','w'))
finish(sc)
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
