import bpy, math, sys, random
from mathutils import Vector
random.seed(313)
args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
OUT = args[0] if args else "/home/claude/tavern/f1.png"
SCALE = int(args[1]) if len(args) > 1 else 50
SAMPLES = int(args[2]) if len(args) > 2 else 64

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
sc.render.resolution_percentage = SCALE
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.cycles.max_bounces = 6

# ---------- materials
def nodes_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; return m, nt, nt.nodes["Principled BSDF"]

def wood(name, base=(0.23,0.12,0.06), dark=(0.10,0.05,0.025), scale=6, rough=0.6, stretch=(1,8,1)):
    m, nt, b = nodes_mat(name); n = nt.nodes; l = nt.links
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = stretch
    wv = n.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = scale; wv.inputs["Distortion"].default_value = 6; wv.inputs["Detail"].default_value = 4
    ns = n.new("ShaderNodeTexNoise"); ns.inputs["Scale"].default_value = 30
    mix = n.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    cr = n.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (*dark,1); cr.color_ramp.elements[1].color = (*base,1)
    l.new(tc.outputs["Object"], mp.inputs["Vector"]); l.new(mp.outputs["Vector"], wv.inputs["Vector"])
    l.new(wv.outputs["Fac"], cr.inputs["Fac"]); l.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.15
    l.new(ns.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def stone(name, c1=(0.32,0.29,0.25), c2=(0.18,0.16,0.14), scale=3.5):
    m, nt, b = nodes_mat(name); n = nt.nodes; l = nt.links
    tc = n.new("ShaderNodeTexCoord")
    vo = n.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = scale; vo.feature = 'DISTANCE_TO_EDGE'
    ns = n.new("ShaderNodeTexNoise"); ns.inputs["Scale"].default_value = 8
    cr = n.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (0.08,0.07,0.06,1)
    cr.color_ramp.elements[1].position = 0.06; cr.color_ramp.elements[1].color = (*c1,1)
    mx = n.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.inputs["Factor"].default_value = 0.35
    l.new(tc.outputs["Object"], vo.inputs["Vector"]); l.new(tc.outputs["Object"], ns.inputs["Vector"])
    l.new(vo.outputs["Distance"], cr.inputs["Fac"])
    l.new(cr.outputs["Color"], mx.inputs["A"]); mx.inputs["B"].default_value = (*c2,1); l.new(ns.outputs["Fac"], mx.inputs["Factor"])
    l.new(mx.outputs["Result"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.85
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6
    l.new(vo.outputs["Distance"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def plain(name, col, rough=0.7, metal=0.0, emit=None, estr=0.0, trans=0.0, alpha=1.0):
    m, nt, b = nodes_mat(name)
    b.inputs["Base Color"].default_value = (*col,1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if emit: b.inputs["Emission Color"].default_value = (*emit,1); b.inputs["Emission Strength"].default_value = estr
    if trans: b.inputs["Transmission Weight"].default_value = trans; b.inputs["IOR"].default_value = 1.45
    return m

M_FLOOR = wood("floor", base=(0.30,0.18,0.09), dark=(0.13,0.07,0.035), scale=3, stretch=(1,10,1))
_n = M_FLOOR.node_tree.nodes; _l = M_FLOOR.node_tree.links
_br = _n.new("ShaderNodeTexBrick"); _br.inputs["Scale"].default_value = 1.0; _br.inputs["Mortar Size"].default_value = 0.008
_br.inputs["Brick Width"].default_value = 1.6; _br.inputs["Row Height"].default_value = 0.22; _br.offset = 0.37
_br.inputs["Color1"].default_value = (1,1,1,1); _br.inputs["Color2"].default_value = (0.75,0.75,0.75,1); _br.inputs["Mortar"].default_value = (0.05,0.05,0.05,1)
_tc = _n.new("ShaderNodeTexCoord"); _l.new(_tc.outputs["Object"], _br.inputs["Vector"])
_mul = _n.new("ShaderNodeMix"); _mul.data_type='RGBA'; _mul.blend_type='MULTIPLY'; _mul.inputs["Factor"].default_value=1.0
_pb = _n["Principled BSDF"]; _src = _pb.inputs["Base Color"].links[0].from_socket
_l.new(_src, _mul.inputs["A"]); _l.new(_br.outputs["Color"], _mul.inputs["B"]); _l.new(_mul.outputs["Result"], _pb.inputs["Base Color"])
M_WOOD = wood("wood", base=(0.25,0.13,0.06), dark=(0.09,0.045,0.02), scale=5)
M_DARK = wood("darkwood", base=(0.10,0.06,0.035), dark=(0.04,0.025,0.015), scale=5, rough=0.5)
M_STONE = stone("stone")
M_PLASTER = plain("plaster", (0.55,0.48,0.38), 0.95)
M_IRON = plain("iron", (0.18,0.16,0.15), 0.45, 0.9)
M_RUST = plain("rust", (0.30,0.12,0.05), 0.8, 0.3)
M_GLASS = plain("glass", (0.9,0.85,0.8), 0.05, trans=1.0)
M_EGG = plain("egg", (0.55,0.04,0.06), 0.35)
M_BRINE = plain("brine", (0.6,0.05,0.08), 0.1, trans=0.85)
M_FIRE = plain("fire", (1,0.5,0.1), 0.5, emit=(1.0,0.45,0.12), estr=40)
M_LAMP = plain("lampglow", (1,0.8,0.5), 0.5, emit=(1.0,0.72,0.38), estr=25)
M_BOARD = plain("board", (0.03,0.035,0.03), 0.9)
M_CHALK = plain("chalk", (0.9,0.9,0.85), 0.9, emit=(0.8,0.8,0.75), estr=0.3)
M_CLOTH = plain("cloth", (0.35,0.28,0.18), 0.95)
M_BLANKET = plain("blanket", (0.32,0.10,0.08), 0.95)
M_SOUP = plain("soup", (0.45,0.30,0.12), 0.4)
M_GROUND = plain("ground", (0.12,0.11,0.10), 0.95)

def box(name, loc, size, mat, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = (size[0]/2, size[1]/2, size[2]/2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat); return o

def cyl(name, loc, r, h, mat, rot=(0,0,0), verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def sphere(name, loc, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=16, ring_count=10)
    o = bpy.context.object; o.name = name; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def plight(loc, energy, col=(1.0,0.7,0.4), r=0.08):
    bpy.ops.object.light_add(type='POINT', location=loc); L = bpy.context.object
    L.data.energy = energy; L.data.color = col; L.data.shadow_soft_size = r; return L


def finish(sc):
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.split('.')[0] not in ("ground","floor","alley","yard"):
            m = o.modifiers.new("bv", 'BEVEL'); m.width = 0.012; m.segments = 2; m.limit_method = 'ANGLE'
