# Phase B v2 — 배선 검증 + 렌더 델타 (shard2용)
# usage: blender -b --factory-startup -noaudio -P phase_b_v2.py -- <shard> <shard_i> <of_K>
import bpy, os, sys, re, csv, math, glob, difflib, mathutils
import numpy as np
from collections import defaultdict

a = sys.argv[sys.argv.index("--")+1:]
SHARD, SH, OF = a[0], int(a[1]), int(a[2])
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TEXROOT = f"{B}/unity_confirmed_{SHARD}"
OUT = f"/workspace/jh/phase_b_{SHARD}"
RENDER = int(os.environ.get("PB_RENDER", "1"))
RES = int(os.environ.get("PB_RES", "256"))

def _n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
def _stem(x): return _n(re.sub(r"\.\d+$", "", os.path.splitext(os.path.basename(x))[0]))
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}
PLACE = ("checker","grid","default","notexture","untitled","none","placeholder")

# ── 입력: map 한 장에 좌표까지 다 있음 ──
rows = defaultdict(list); mesh_of = {}
with open(f"{B}/shards/{SHARD}_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1": continue
        mesh_of[r["sha256"]] = r["mesh_path"]
        if _n(r["tex_slot"]) in ALB:
            rows[r["sha256"]].append(r)
items = sorted(mesh_of)
items = [x for i, x in enumerate(items) if i % OF == SH]

def live_img(n):
    if not (n.type == "TEX_IMAGE" and n.image): return False
    if getattr(n.image, "source", "") == "GENERATED": return False
    if _stem(n.image.name) in PLACE: return False
    fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
    return bool(n.image.packed_file or (fp and os.path.exists(fp)))

def count_tex():
    return sum(1 for m in bpy.data.materials
               if m.use_nodes and m.node_tree and any(live_img(n) for n in m.node_tree.nodes))

def has_live(m):
    return m.use_nodes and m.node_tree and any(live_img(n) for n in m.node_tree.nodes)

def wire(m, img):
    if has_live(m): return False
    m.use_nodes = True; nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not b: return False
    if b.inputs["Alpha"].default_value == 0: b.inputs["Alpha"].default_value = 1.0
    m.blend_method = "OPAQUE"
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"]); return True

def repoint(m, img, texfile):
    if not (m.use_nodes and m.node_tree): return False
    ok = False
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and _stem(n.image.name) == _stem(texfile) and not live_img(n):
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

_cam = [None]
def setup_scene():
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
    sc.render.film_transparent = True          # 배경 알파=0 → 물체 마스크
    sc.render.resolution_x = RES; sc.render.resolution_y = RES
    sc.render.image_settings.color_mode = "RGBA"

def render_np(png):
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(png)
    px = np.array(im.pixels[:], dtype=np.float32).reshape(-1, 4)
    bpy.data.images.remove(im)
    try: os.remove(png)
    except Exception: pass
    return px

def metrics(a_px, b_px):
    """물체 영역만 비교 → (픽셀변화율, 색다양성 증가, 단색비율 변화)"""
    mask = (a_px[:, 3] > 0.1) | (b_px[:, 3] > 0.1)
    if mask.sum() < 20: return 0.0, 0.0, 0.0
    A, Bp = a_px[mask][:, :3], b_px[mask][:, :3]
    diff = float(np.abs(A - Bp).mean())
    dstd = float(Bp.std() - A.std())
    def flat(x):
        q = np.round(x * 12).astype(np.int16)
        _, cnt = np.unique(q, axis=0, return_counts=True)
        return float(cnt.max() / len(q))
    return diff, dstd, float(flat(A) - flat(Bp))

# ── 실행 ──
os.makedirs(OUT, exist_ok=True)
part = f"{OUT}/part_{SH}.csv"; mark = f"{OUT}/cur_{SH}.txt"
done = set()
if os.path.exists(part):
    for r in csv.reader(open(part)):
        if r: done.add(r[0])
crashed = open(mark).read().strip() if os.path.exists(mark) else ""
fh = open(part, "a", newline=""); w = csv.writer(fh)
TMPIMG = f"/tmp/pb_{SHARD}_{SH}"

for sha in items:
    if sha in done: continue
    if sha == crashed:
        w.writerow([sha, mesh_of[sha], 0, 0, 0, 0, 0, "IMPORT_CRASH", "", 0, 0, 0]); fh.flush(); continue
    open(mark, "w").write(sha)
    mp = os.path.join(B, f"shards/{SHARD}", mesh_of[sha])
    rs, seen = [], set()
    for r in rows.get(sha, []):
        k = (r["mat_path"], r["texture_path"])
        if k in seen: continue
        seen.add(k); rs.append(r)
    try:
        imp(mp); before = count_tex()
        if RENDER:
            setup_scene(); pxa = render_np(TMPIMG + "_a.png")
        by_coord = by_fb = 0
        for r in rs:
            tp = os.path.join(TEXROOT, r["repo"], r["texture_path"])
            if not os.path.exists(tp): continue
            img = bpy.data.images.load(tp)
            ok = False
            # ① 좌표 우선 (map에 이미 들어있음)
            if r["fbx_material_name"]:
                for m in bpy.data.materials:
                    if _n(m.name) == _n(r["fbx_material_name"]) or _stem(m.name) == _stem(r["fbx_material_name"]):
                        if wire(m, img): ok = True
            if not ok and r["gameobject_name"]:
                for o in obj_match(r["gameobject_name"]):
                    if wire(slot_of(o, r["slot_index"]), img): ok = True
            if ok: by_coord += 1; continue
            # ② 폴백
            f2 = any(repoint(m, img, r["texture_path"]) for m in bpy.data.materials)
            if not f2:
                mn2 = _stem(r["mat_path"])
                for m in bpy.data.materials:
                    a2 = _n(m.name)
                    if a2 and (a2.startswith(mn2[:12]) or mn2.startswith(a2[:12])):
                        if wire(m, img): f2 = True
            if not f2 and r["slot_index"] not in ("", "None"):
                try: i2 = int(r["slot_index"])
                except Exception: i2 = None
                if i2 is not None:
                    for o in bpy.data.objects:
                        if o.type == "MESH" and len(o.material_slots) > i2 and o.material_slots[i2].material:
                            if wire(o.material_slots[i2].material, img): f2 = True
            if not f2 and len(rs) == 1:
                ms_all = [ms for o in bpy.data.objects if o.type == "MESH" for ms in o.material_slots]
                if len(set(ms.material for ms in ms_all if ms.material)) <= 1:
                    for o in bpy.data.objects:
                        if o.type != "MESH": continue
                        if not o.material_slots: o.data.materials.append(bpy.data.materials.new("c"))
                        for ms in o.material_slots:
                            if ms.material is None: ms.material = bpy.data.materials.new("c")
                            if wire(ms.material, img): f2 = True
            if f2: by_fb += 1
        after = count_tex()
        diff = dstd = dflat = 0.0
        if RENDER:
            pxb = render_np(TMPIMG + "_b.png")
            diff, dstd, dflat = metrics(pxa, pxb)
        # ── 판정 ──
        if after < before: v, why = "REGRESSION", ""
        elif after > before:
            # 분산 감소는 정상(무텍스처 회색+조명 → 평평한 텍스처)이므로 판정에 쓰지 않고 컬럼으로만 기록
            if RENDER and diff < 0.002: v, why = "NO_VISUAL_EFFECT", "render_delta~0"
            else: v, why = "APPLIED", ("coord" if by_coord else "fallback")
        elif before > 0: v, why = "HELD", ""
        else: v, why = "NO_TEXTURE", ("NO_ALBEDO" if not rs else "NOT_APPLIED")
        w.writerow([sha, mesh_of[sha], len(rs), before, after, by_coord, by_fb, v, why,
                    round(diff, 5), round(dstd, 5), round(dflat, 5)])
    except Exception as e:
        w.writerow([sha, mesh_of[sha], 0, 0, 0, 0, 0, "IMPORT_FAIL", type(e).__name__, 0, 0, 0])
    fh.flush()
fh.close()
if os.path.exists(mark): os.remove(mark)
print("PART_DONE", SH)
