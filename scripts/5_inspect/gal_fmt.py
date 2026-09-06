# 포맷별 표본 갤러리 — before/after 렌더 (검증 통과분에서 추출)
# usage: blender -b --factory-startup -noaudio -P gal_fmt.py -- <shard> <N per ext> <seed> <shard_i> <of_K>
import bpy, os, sys, re, csv, math, glob, random, difflib, mathutils
from collections import defaultdict

a = sys.argv[sys.argv.index("--")+1:]
SHARD, NPE, SEED, SH, OF = a[0], int(a[1]), int(a[2]), int(a[3]), int(a[4])
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TEXROOT = f"{B}/unity_confirmed_{SHARD}"
VIEW = f"/workspace/jh/view_{SHARD}"
RES = 400

def _n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
def _stem(x): return _n(re.sub(r"\.\d+$", "", os.path.splitext(os.path.basename(x))[0]))
PLACE = ("checker","grid","default","notexture","untitled","none","placeholder")

rows = defaultdict(list); meta = {}
with open(f"{B}/shards/{SHARD}_appearance_ready.csv") as f:
    for r in csv.DictReader(f):
        rows[r["sha256"]].append(r)
        meta[r["sha256"]] = (r["mesh_path"], r["verdict"], r["wired_by"])
by_ext = defaultdict(list)
for sha, (mp, v, wb) in meta.items():
    by_ext[os.path.splitext(mp)[1].lower().lstrip(".")].append(sha)
picks = []
for ext in sorted(by_ext):
    lst = sorted(by_ext[ext]); random.Random(SEED).shuffle(lst)
    picks += [(ext, s) for s in lst[:NPE]]
picks = picks[SH::OF]

def live_img(n):
    if not (n.type == "TEX_IMAGE" and n.image): return False
    if getattr(n.image, "source", "") == "GENERATED": return False
    if _stem(n.image.name) in PLACE: return False
    fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
    return bool(n.image.packed_file or (fp and os.path.exists(fp)))
def has_live(m): return m.use_nodes and m.node_tree and any(live_img(n) for n in m.node_tree.nodes)
def wire(m, img):
    if has_live(m): return False
    m.use_nodes = True; nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not b: return False
    if b.inputs["Alpha"].default_value == 0: b.inputs["Alpha"].default_value = 1.0
    m.blend_method = "OPAQUE"
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"]); return True
def repoint(m, img, tf):
    if not (m.use_nodes and m.node_tree): return False
    ok = False
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and _stem(n.image.name) == _stem(tf) and not live_img(n):
            n.image = img; ok = True
    return ok
def obj_match(nm):
    t = _n(nm)
    if not t: return []
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    for f in (lambda o: _n(o.name) == t,
              lambda o: _n(o.name) and (t.startswith(_n(o.name)) or _n(o.name).startswith(t)),
              lambda o: _n(o.name) and (_n(o.name) in t or t in _n(o.name))):
        hit = [o for o in objs if f(o)]
        if hit: return hit
    sc = [(difflib.SequenceMatcher(None, _n(o.name), t).ratio(), o) for o in objs if _n(o.name)]
    sc = [x for x in sc if x[0] >= 0.55]
    if not sc: return []
    bst = max(x[0] for x in sc)
    return [o for r, o in sc if r >= bst - 0.05]
def slot_of(o, si):
    try: i = int(si)
    except Exception: i = 0
    if not o.material_slots: o.data.materials.append(bpy.data.materials.new(o.name + "_c"))
    if i >= len(o.material_slots): i = 0
    if o.material_slots[i].material is None:
        o.material_slots[i].material = bpy.data.materials.new(o.name + "_c")
    return o.material_slots[i].material
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
    cam.rotation_euler = (cam.location - c).to_track_quat("Z", "Y").to_euler()
    cam.data.clip_end = max(1000, r*10)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(40)); sun.data.energy = 4
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = RES; sc.render.resolution_y = RES
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)

os.makedirs(VIEW, exist_ok=True)
cards = []
for ext, sha in picks:
    mp, verdict, wb = meta[sha]
    path = os.path.join(B, f"shards/{SHARD}", mp)
    if not os.path.exists(path): continue
    name = os.path.splitext(os.path.basename(mp))[0].replace(" ", "_")
    cid = f"{ext}_{sha[:8]}_{name}"[:64]
    d = os.path.join(VIEW, cid); os.makedirs(d, exist_ok=True)
    seen, rs = set(), []
    for r in rows[sha]:
        k = (r["mat_path"], r["texture_path"])
        if k in seen: continue
        seen.add(k); rs.append(r)
    try:
        imp(path); render(os.path.join(d, "before.png"))
        imp(path); nw = 0
        for r in rs:
            tp = os.path.join(TEXROOT, r["repo"], r["texture_path"])
            if not os.path.exists(tp): continue
            img = bpy.data.images.load(tp); ok = False
            if r["fbx_material_name"]:
                for m in bpy.data.materials:
                    if _n(m.name) == _n(r["fbx_material_name"]) or _stem(m.name) == _stem(r["fbx_material_name"]):
                        if wire(m, img): ok = True
            if not ok and r["gameobject_name"]:
                for o in obj_match(r["gameobject_name"]):
                    if wire(slot_of(o, r["slot_index"]), img): ok = True
            if not ok:
                ok = any(repoint(m, img, r["texture_path"]) for m in bpy.data.materials)
            if not ok:
                mn2 = _stem(r["mat_path"])
                for m in bpy.data.materials:
                    a2 = _n(m.name)
                    if a2 and (a2.startswith(mn2[:12]) or mn2.startswith(a2[:12])):
                        if wire(m, img): ok = True
            if ok: nw += 1
        render(os.path.join(d, "after.png"))
        cards.append((ext, cid, mp, len(rs), nw, verdict, wb))
        print("OK", cid, flush=True)
    except Exception as e:
        print("FAIL", cid, type(e).__name__, flush=True)
with open(f"{VIEW}/.cards_{SH}.tsv", "w") as f:
    for c in cards: f.write("\t".join(map(str, c)) + "\n")
print("SHARD_DONE", SH, len(cards))
