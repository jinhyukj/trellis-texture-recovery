# Phase A 좌표 A/B 비교: 왼쪽=추측 규칙 배선 / 오른쪽=좌표 기반 배선
# usage: blender -b --factory-startup -noaudio -P coordcompare.py -- <N> <seed> [shard] [of]
import bpy, os, sys, re, csv, glob, math, random, mathutils, difflib
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
VIEW = "/workspace/jh/view"
a = sys.argv[sys.argv.index("--")+1:]
N = int(a[0]); SEED = int(a[1]); SHARD = int(a[2]) if len(a) > 2 else 0; OFK = int(a[3]) if len(a) > 3 else 1
def _n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
def _stem(x): return _n(re.sub(r"\.\d+$", "", os.path.splitext(os.path.basename(x))[0]))
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}

coords = defaultdict(list)
for f in glob.glob("/workspace/jh/phase_a/.done/*.csv"):
    for r in csv.reader(open(f)):
        if len(r) >= 7 and r[3] in ("GO", "FBXMAT"):
            coords[r[0]].append((r[3], r[4], r[5], r[6]))   # type, slot, name, mat_path
albs = defaultdict(list); sp = {}
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1" or _n(r["tex_slot"]) not in ALB: continue
        albs[r["sha256"]].append((r["mat_path"], r["texture_path"], r["repo"]))
        sp[r["sha256"]] = r["shard_path"]
cand = [s for s in coords if s in albs]
random.seed(SEED); random.shuffle(cand)
cand = cand[:N][SHARD::OFK]

def imp(p):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lo = p.lower()
    if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=p)
    elif lo.endswith(".obj"):
        try: bpy.ops.wm.obj_import(filepath=p)
        except AttributeError: bpy.ops.import_scene.obj(filepath=p)
    elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=p)
    elif lo.endswith(".dae"): bpy.ops.wm.collada_import(filepath=p)
    else: raise RuntimeError("fmt")

def live(m):
    if not m.use_nodes or not m.node_tree: return False
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            if getattr(n.image, "source", "") == "GENERATED": continue
            if _stem(n.image.name) in ("checker","grid","default","notexture","untitled","none"): continue
            fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
            if n.image.packed_file or (fp and os.path.exists(fp)): return True
    return False

def wire(m, img):
    if live(m): return False
    m.use_nodes = True; nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf: return False
    if bsdf.inputs["Alpha"].default_value == 0: bsdf.inputs["Alpha"].default_value = 1.0
    m.blend_method = "OPAQUE"
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"]); return True

def repoint(m, img, texfile):
    if not m.use_nodes or not m.node_tree: return False
    ok = False
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and _stem(n.image.name) == _stem(texfile):
            fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
            if not n.image.packed_file and not (fp and os.path.exists(fp)):
                n.image = img; ok = True
    return ok

def render(png):
    sc = bpy.context.scene
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
    mn = mathutils.Vector((1e9,)*3); mx = mathutils.Vector((-1e9,)*3)
    for o in bpy.data.objects:
        if o.type == "MESH":
            for v in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(v)
                mn = mathutils.Vector(map(min, mn, w)); mx = mathutils.Vector(map(max, mx, w))
    c = (mn+mx)/2; r = max((mx-mn).length, 0.1)
    cam.location = c + mathutils.Vector((r*0.8, -r*0.8, r*0.45))
    cam.rotation_euler = (cam.location-c).to_track_quat("Z", "Y").to_euler()
    cam.data.clip_end = max(1000, r*10)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(40)); sun.data.energy = 4
    sc.render.engine = "BLENDER_EEVEE"; sc.render.resolution_x = 380; sc.render.resolution_y = 380
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)

out = []
for sha in cand:
    rows = []
    seen = set()
    for mp, tp, repo in albs[sha]:
        if (mp, tp) in seen: continue
        seen.add((mp, tp)); rows.append((mp, tp, repo))
    name = os.path.splitext(os.path.basename(sp[sha]))[0].replace(" ", "_")
    cid = f"{sha[:10]}_{name}"[:60]
    d = os.path.join(VIEW, "cmp", cid); os.makedirs(d, exist_ok=True)
    mesh = os.path.join(B, "shards/shard1", sp[sha])
    try:
        # A: 추측 규칙 (이름 유사도 + 슬롯 + 단일재질 전체적용)
        imp(mesh); na = 0
        for mp, tp, repo in rows:
            img = bpy.data.images.load(os.path.join(B, "unity_confirmed", repo, tp))
            done = any(repoint(m, img, tp) for m in bpy.data.materials)
            if not done:
                mn2 = _stem(mp)
                for m in bpy.data.materials:
                    if _n(m.name)[:12] and (_n(m.name).startswith(mn2[:12]) or mn2.startswith(_n(m.name)[:12])):
                        if wire(m, img): done = True
            if not done and len(rows) == 1:
                for o in bpy.data.objects:
                    if o.type != "MESH": continue
                    if not o.material_slots: o.data.materials.append(bpy.data.materials.new("c"))
                    for ms in o.material_slots:
                        if ms.material is None: ms.material = bpy.data.materials.new("c")
                        if wire(ms.material, img): done = True
            if done: na += 1
        render(os.path.join(d, "a.png"))
        # B: Phase A 좌표 기반
        imp(mesh); nb = 0
        cmap = defaultdict(list)
        for ct, si, nm, mp in coords[sha]: cmap[mp].append((ct, si, nm))
        for mp, tp, repo in rows:
            img = bpy.data.images.load(os.path.join(B, "unity_confirmed", repo, tp))
            done = False
            for ct, si, nm in cmap.get(mp, []):
                if ct == "FBXMAT":
                    for m in bpy.data.materials:
                        if _n(m.name) == _n(nm) or _stem(m.name) == _stem(nm):
                            if wire(m, img): done = True
                elif ct == "GO" and nm:
                    for o in bpy.data.objects:
                        if o.type != "MESH": continue
                        if _n(o.name) != _n(nm): continue
                        try: idx = int(si)
                        except Exception: idx = 0
                        if not o.material_slots: o.data.materials.append(bpy.data.materials.new("c"))
                        if idx < len(o.material_slots):
                            if o.material_slots[idx].material is None:
                                o.material_slots[idx].material = bpy.data.materials.new("c")
                            if wire(o.material_slots[idx].material, img): done = True
            if done: nb += 1
        render(os.path.join(d, "b.png"))
        out.append((cid, sp[sha], len(rows), na, nb))
        print("OK", cid, na, nb, flush=True)
    except Exception as e:
        print("FAIL", cid, type(e).__name__, flush=True)
with open(f"{VIEW}/.cmp_{SHARD}.tsv", "w") as f:
    for c in out: f.write("\t".join(map(str, c)) + "\n")
print("SHARD_DONE", SHARD, len(out))
