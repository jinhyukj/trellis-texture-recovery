import bpy,sys,os
p=sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.open_mainfile(filepath=p)
for o in bpy.data.objects:
    if o.type=="MESH": print("OBJ",o.name,"slots:",[(ms.material.name if ms.material else None) for ms in o.material_slots])
for m in bpy.data.materials:
    imgs=[]
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type=="TEX_IMAGE" and n.image:
                fp=bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
                imgs.append((n.image.name, bool(n.image.packed_file), os.path.exists(fp) if fp else False))
    print("MAT",m.name,"nodes:",m.use_nodes,"imgs:",imgs)
