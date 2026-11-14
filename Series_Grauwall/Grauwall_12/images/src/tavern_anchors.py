import bpy, json, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
def compute(loc, lens, tgt, anchors, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object; sc.camera = cam; cam.data.lens = lens
    d = Vector(tgt) - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    json.dump({k: (lambda c: [c.x, 1-c.y])(world_to_camera_view(sc, cam, Vector(v))) for k, v in anchors.items()}, open(out, 'w'))
W,D,T,CY,px=14.0,10.0,0.4,7.2,7.0; jx,jy=3.35,7.15; CXo=W+T
compute((21.5,-9.0,15.5),33,(9.8,5.6,0.4),{"front":(4.8,-0.3,1.0),"desk":(7.2,1.2,1.1),"counter":(8.0,CY,1.2),"jar":(jx,jy,1.6),"nails":(px,D-0.45,2.0),"barrels":(8.8,D-0.55,1.5),
  "board":(5.9,D-0.05,2.2),"hearth":(W-0.45,4.2,1.9),"tables":(5.0,4.4,0.8),"stairs":(0.75,7.5,2.0),"storage":(0.6,8.6,0.6),"bench":(0.45,0.9,0.8),
  "backdoor":(12.6,D,2.0),"well":(CXo+1.8,5.0,1.9),"stable":(CXo+3.8,8.9,2.6)},"f1_anchors.json")
W=14.0
compute((16.5,-9.5,15.0),35,(6.8,5.0,0.3),{"archive":(2.6,3.4,0.9),"registry":(0.32,7.3,0.3),"gm":(7.6,2.0,0.9),"bowbox":(5.3,6.6,0.6),"master":(11.0,6.0,0.6),
  "lulu":(13.0,6.0,0.6),"corridor":(8.0,9.1,0.1),"stairs":(0.75,9.1,0.1),"window":(W,6.4,1.1)},"f2_anchors.json")
