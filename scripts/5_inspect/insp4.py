import bpy, sys, os
p = sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.read_factory_settings(use_empty=True)
lo = p.lower()
try:
    if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=p)
    elif lo.endswith(".obj"):
        try: bpy.ops.wm.obj_import(filepath=p)
        except AttributeError: bpy.ops.import_scene.obj(filepath=p)
    elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=p)
except Exception as e:
    print("IMPORT_FAIL", e); raise SystemExit
nmesh = 0
for o in bpy.data.objects:
    if o.type != "MESH": continue
    nmesh += 1
    uv = len(o.data.uv_layers)
    slots = [(ms.material.name if ms.material else None) for ms in o.material_slots]
    if nmesh <= 6:
        print(f"OBJ {o.name!r} UV={uv} verts={len(o.data.vertices)} slots={slots}")
print("MESH수:", nmesh)
for m in bpy.data.materials:
    imgs = []
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
                imgs.append((n.image.name, "packed" if n.image.packed_file else ("live" if fp and os.path.exists(fp) else "broken")))
    print(f"MAT {m.name!r} nodes={m.use_nodes} imgs={imgs}")
