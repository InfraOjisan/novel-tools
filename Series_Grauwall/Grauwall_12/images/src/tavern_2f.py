exec(open('/home/claude/tavern/common.py').read())
# ---------- second floor (same footprint 14 x 10). Walls cut low for the cutaway, north exterior wall full.
W, D, HW, HC = 14.0, 10.0, 2.6, 1.25
T = 0.35; t = 0.14
box("ground", (W/2, D/2, -0.06), (40, 40, 0.1), M_GROUND)
box("floor", (W/2, D/2, 0.0), (W, D, 0.04), M_FLOOR)
box("wall_n", (W/2, D+T/2, HW/2), (W+2*T, T, HW), M_STONE)
box("wall_w", (-T/2, D/2, HC/2), (T, D, HC), M_STONE)
box("wall_s", (W/2, -T/2, HC/2), (W+2*T, T, HC), M_STONE)
box("wall_e", (W+T/2, D/2, HC/2), (T, D+2*T, HC), M_STONE)
for x in (3.5, 7.0, 10.5): box("post_n", (x, D-0.08, HW/2), (0.22, 0.2, HW), M_DARK)
# corridor along the north (y 8.2..10). Partition wall at y=8.2 with door gaps.
CY0 = 8.2
def pwall(x0, x1, y):  # plaster partition along x
    box("pw", ((x0+x1)/2, y, HC/2), (x1-x0, t, HC), M_PLASTER)
def pwall_y(y0, y1, x):
    box("pw", (x, (y0+y1)/2, HC/2), (t, y1-y0, HC), M_PLASTER)
# rooms: archive x0..4.6 ; master-of-guild x4.6..14 (L), small rooms x10..12 / 12..14 at y4.6..8.2
doors = [(2.9, 3.8), (5.2, 6.1), (10.5, 11.3), (12.6, 13.4)]
xs = [1.5] + [v for d in doors for v in d] + [W]
for i in range(0, len(xs), 2): pwall(xs[i], xs[i+1], CY0)
pwall_y(0, CY0, 4.6)
pwall_y(4.6, CY0, 10.0); pwall_y(4.6, CY0, 12.0)
pwall(10.0, W, 4.6)
# stair opening at the north-west (stairs arrive here from below)
box("stairwell", (0.75, 9.1, 0.02), (1.1, 1.6, 0.03), plain("hole", (0.01,0.01,0.01), 0.9))
box("rail", (1.4, 9.1, 0.5), (0.06, 1.6, 0.06), M_DARK); box("railtop", (1.4, 9.1, 0.95), (0.08, 1.6, 0.06), M_DARK)
for y in (8.4, 9.8): box("railpost", (1.4, y, 0.48), (0.08, 0.08, 0.95), M_DARK)
# corridor runner
box("runner", (8.0, 9.1, 0.03), (11.5, 0.8, 0.02), plain("runner", (0.32,0.10,0.07), 0.95))
# --- archive (書庫): shelves on the walls, long table, registry on the bottom shelf at the back
for i in range(3):
    y0 = 1.4+i*2.2
    box("shelfback", (0.04, y0, 1.0), (0.06, 1.9, 2.0), M_DARK)
    for dy in (-0.95, 0.95): box("shelfside", (0.25, y0+dy, 1.0), (0.42, 0.05, 2.0), M_DARK)
    for lv2 in range(5): box("shelfboard", (0.25, y0, 0.12+lv2*0.5), (0.42, 1.9, 0.04), M_DARK)
    for lv in range(4):
        z = 0.15+lv*0.5
        for k in range(7):
            box("book", (0.26, 0.62+i*2.2+k*0.25, z+0.17), (0.28, 0.16+random.random()*0.05, 0.3+random.random()*0.08),
                plain(f"bk{i}{lv}{k}", random.choice([(0.25,0.12,0.06),(0.15,0.10,0.07),(0.30,0.22,0.12),(0.12,0.12,0.10)]), 0.8))
box("table_a", (2.6, 3.4, 0.74), (1.2, 3.0, 0.08), M_WOOD)
for dx in (-0.5,0.5):
    for dy in (-1.3,1.3): box("leg", (2.6+dx, 3.4+dy, 0.36), (0.08,0.08,0.72), M_DARK)
box("registry", (0.32, 7.3, 0.12), (0.4, 0.55, 0.12), plain("cowhide", (0.38,0.22,0.12), 0.7))
box("registryshelf", (0.25, 7.3, 0.05), (0.45, 1.6, 0.05), M_DARK)
box("dust", (0.32, 7.3, 0.185), (0.38, 0.5, 0.004), plain("dust", (0.55,0.5,0.42), 1.0))
# --- guild master's room (組合長の部屋): desk, chair, bow box, small window
box("desk", (7.6, 2.0, 0.74), (1.8, 0.9, 0.08), M_DARK)
for dx in (-0.8,0.8):
    for dy in (-0.38,0.38): box("dleg", (7.6+dx, 2.0+dy, 0.36), (0.08,0.08,0.72), M_DARK)
box("chair", (7.6, 2.75, 0.45), (0.5, 0.5, 0.06), M_WOOD); box("chairback", (7.6, 3.0, 0.75), (0.5, 0.06, 0.6), M_WOOD)
box("papers", (7.4, 1.9, 0.79), (0.5, 0.35, 0.02), plain("paper", (0.82,0.78,0.66), 0.9))
box("bowbox", (5.3, 6.6, 0.25), (0.45, 2.2, 0.4), M_WOOD); box("bowlid", (5.3, 6.6, 0.47), (0.5, 2.25, 0.05), M_DARK)
box("cabinet", (9.6, 6.9, 0.8), (0.6, 1.6, 1.6), M_DARK)
cyl("lamp2", (8.3, 1.8, 0.86), 0.05, 0.1, M_IRON, verts=12); sphere("lf2", (8.3, 1.8, 0.95), 0.03, M_LAMP); plight((8.3, 1.8, 1.1), 40)
box("rug", (8.5, 3.0, 0.025), (3.5, 2.4, 0.01), plain("rug", (0.28,0.16,0.08), 0.95))
# --- small rooms: master's (x10..12) and the empty one at the end (x12..14), low window, scratched bed legs
def bedroom(x0, x1, blanket_folded, scratched):
    cx = (x0+x1)/2
    box("bed", (cx, 6.0, 0.25), (0.95, 1.9, 0.12), M_WOOD)
    for dx in (-0.4,0.4):
        for dy in (-0.85,0.85): box("bedleg", (cx+dx, 6.0+dy, 0.1), (0.08,0.08,0.2), M_DARK)
    box("mattress", (cx, 6.0, 0.36), (0.85, 1.8, 0.1), M_CLOTH)
    if blanket_folded: box("blanket", (cx, 5.35, 0.45), (0.8, 0.4, 0.1), M_BLANKET)
    else: box("blanket", (cx, 6.2, 0.43), (0.83, 1.3, 0.04), plain("blanket2", (0.55,0.55,0.5), 0.95))
    box("stand", (cx+0.6, 7.6, 0.35), (0.4, 0.4, 0.7), M_WOOD)
    if scratched:
        for k in range(4): box("scratch", (cx-0.44, 6.85, 0.05+k*0.03), (0.002, 0.06, 0.004), plain("scr", (0.7,0.6,0.45), 0.9))
bedroom(10.0, 12.0, True, False)
bedroom(12.0, W, False, True)
box("lowwindow", (W+0.02, 6.4, 0.75), (0.06, 0.8, 0.6), plain("night", (0.05,0.08,0.15), 0.1, emit=(0.15,0.2,0.35), estr=1.0))
box("sill", (W-0.08, 6.4, 0.43), (0.16, 0.9, 0.05), M_DARK)
plight((11.0, 6.4, 1.6), 25); plight((13.0, 6.4, 1.6), 10, (0.6,0.7,1.0))
# corridor lamps
for x in (4.0, 9.0): sphere("hl", (x, 9.1, 2.1), 0.06, M_LAMP); plight((x, 9.1, 2.0), 90)
plight((2.6, 3.4, 2.0), 90); plight((7.6, 4.0, 2.2), 70)
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True
bg = wd.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.012,0.016,0.03,1)
bpy.ops.object.light_add(type='AREA', location=(7, 4, 12)); A = bpy.context.object; A.data.energy = 2600; A.data.size = 16; A.data.color = (0.62,0.7,0.95)
bpy.ops.object.camera_add(location=(16.5, -9.5, 15.0)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 35
tgt = Vector((6.8, 5.0, 0.3)); d = tgt - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = OUT
import json
from bpy_extras.object_utils import world_to_camera_view
anchors = {"archive":(2.6,3.4,0.9),"registry":(0.32,7.3,0.3),"gm":(7.6,2.0,0.9),"bowbox":(5.3,6.6,0.6),"master":(11.0,6.0,0.6),
  "lulu":(13.0,6.0,0.6),"corridor":(8.0,9.1,0.1),"stairs":(0.75,9.1,0.1),"window":(W,6.4,1.1)}
out = {k: (lambda co: [co.x, 1-co.y])(world_to_camera_view(sc, cam, Vector(v))) for k, v in anchors.items()}
json.dump(out, open(OUT.rsplit('.',1)[0]+'_anchors.json','w'))
finish(sc)
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
