# Phase B — 배선 검증: before/after 재질 그래프 계수로 판정 확정
# 최종 적용 규칙(좌표 우선 → 폴백, fill-only)을 그대로 구현
# usage: blender -b --factory-startup -noaudio -P phase_b.py -- <shard_i> <of_K>
import bpy, os, sys, re, csv, glob, difflib
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OUT = "/workspace/jh/phase_b"
a = sys.argv[sys.argv.index("--")+1:]
SH, OF = int(a[0]), int(a[1])

def _n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
def _stem(x): return _n(re.sub(r"\.\d+$", "", os.path.splitext(os.path.basename(x))[0]))
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}
PLACEHOLDER = ("checker","grid","default","notexture","untitled","none","placeholder")

# ── 입력 ──
albs = defaultdict(list); sp = {}
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1": continue
        sp[r["sha256"]] = r["shard_path"]
        if _n(r["tex_slot"]) in ALB:
            albs[r["sha256"]].append((r["mat_path"], r["texture_path"], r["repo"], r["slot_index"]))
coords = defaultdict(list)
cf = f"{B}/shards/shard1_binding_coords.csv"
if os.path.exists(cf):
    for r in csv.DictReader(open(cf)):
        if r["coord_type"] in ("GO", "FBXMAT"):
            coords[r["sha256"]].append((r["coord_type"], r["slot_index"], r["name"], r["mat_path"]))

items = sorted(sp)
items = [x for i, x in enumerate(items) if i % OF == SH]

# ── 규칙 구현 ──
def live_img(n):
    if not (n.type == "TEX_IMAGE" and n.image): return False
    if getattr(n.image, "source", "") == "GENERATED": return False
    if _stem(n.image.name) in PLACEHOLDER: return False
    fp = bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
    return bool(n.image.packed_file or (fp and os.path.exists(fp)))

def count_textured():
    """Base Color 에 유효 이미지가 연결된 재질 수"""
    c = 0
    for m in bpy.data.materials:
        if not (m.use_nodes and m.node_tree): continue
        if any(live_img(n) for n in m.node_tree.nodes): c += 1
    return c

def has_live(m):
    return m.use_nodes and m.node_tree and any(live_img(n) for n in m.node_tree.nodes)

def wire(m, img):
    if has_live(m): return False
    m.use_nodes = True; nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf: return False
    if bsdf.inputs["Alpha"].default_value == 0: bsdf.inputs["Alpha"].default_value = 1.0
    m.blend_method = "OPAQUE"
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"]); return True

def repoint(m, img, texfile):
    if not (m.use_nodes and m.node_tree): return False
    ok = False
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and _stem(n.image.name) == _stem(texfile) and not live_img(n):
            n.image = img; ok = True
    return ok

def obj_match(nm):
    """GameObject 이름 → mesh 오브젝트 (완전→접두/포함→유사도). 인스턴스 접미사 대응"""
    t = _n(nm)
    if not t: return []
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    ex = [o for o in objs if _n(o.name) == t]
    if ex: return ex
    pre = [o for o in objs if _n(o.name) and (t.startswith(_n(o.name)) or _n(o.name).startswith(t))]
    if pre: return pre
    inc = [o for o in objs if _n(o.name) and (_n(o.name) in t or t in _n(o.name))]
    if inc: return inc
    sc = [(difflib.SequenceMatcher(None, _n(o.name), t).ratio(), o) for o in objs if _n(o.name)]
    sc = [x for x in sc if x[0] >= 0.55]
    if not sc: return []
    best = max(x[0] for x in sc)
    return [o for r, o in sc if r >= best - 0.05]

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

# ── 실행 ──
os.makedirs(OUT, exist_ok=True)
part = f"{OUT}/part_{SH}.csv"; mark = f"{OUT}/cur_{SH}.txt"
done = set()
if os.path.exists(part):
    for r in csv.reader(open(part)):
        if r: done.add(r[0])
crashed = open(mark).read().strip() if os.path.exists(mark) else ""
fh = open(part, "a", newline=""); w = csv.writer(fh)

for sha in items:
    if sha in done: continue
    if sha == crashed:
        w.writerow([sha, sp[sha], 0, 0, 0, 0, 0, 0, "IMPORT_CRASH", ""]); fh.flush(); continue
    open(mark, "w").write(sha)
    rows = []
    seen = set()
    for mp, tp, repo, si in albs.get(sha, []):
        if (mp, tp) in seen: continue
        seen.add((mp, tp)); rows.append((mp, tp, repo, si))
    path = os.path.join(B, "shards/shard1", sp[sha])
    try:
        imp(path); before = count_textured()   # 읽기만 하므로 재임포트 불필요
        by_coord = by_fb = held = 0
        cmap = defaultdict(list)
        for ct, si, nm, mp in coords.get(sha, []): cmap[mp].append((ct, si, nm))
        for mp, tp, repo, si in rows:
            tpath = os.path.join(B, "unity_confirmed", repo, tp)
            if not os.path.exists(tpath): continue
            img = bpy.data.images.load(tpath)
            done_c = False
            # ① 좌표 우선
            for ct, csi, nm in cmap.get(mp, []):
                if ct == "FBXMAT":
                    for m in bpy.data.materials:
                        if _n(m.name) == _n(nm) or _stem(m.name) == _stem(nm):
                            if wire(m, img): done_c = True
                elif ct == "GO" and nm:
                    for o in obj_match(nm):
                        if wire(slot_of(o, csi), img): done_c = True
            if done_c: by_coord += 1; continue
            # ② 폴백
            done_f = any(repoint(m, img, tp) for m in bpy.data.materials)
            if not done_f:
                mn = _stem(mp)
                for m in bpy.data.materials:
                    a2 = _n(m.name)
                    if a2 and (a2.startswith(mn[:12]) or mn.startswith(a2[:12])):
                        if wire(m, img): done_f = True
            if not done_f and si not in ("", "None"):
                try: i2 = int(si)
                except Exception: i2 = None
                if i2 is not None:
                    for o in bpy.data.objects:
                        if o.type == "MESH" and len(o.material_slots) > i2 and o.material_slots[i2].material:
                            if wire(o.material_slots[i2].material, img): done_f = True
            if not done_f and len(rows) == 1:
                ms_all = [ms for o in bpy.data.objects if o.type == "MESH" for ms in o.material_slots]
                if len(set(ms.material for ms in ms_all if ms.material)) <= 1:
                    for o in bpy.data.objects:
                        if o.type != "MESH": continue
                        if not o.material_slots: o.data.materials.append(bpy.data.materials.new("c"))
                        for ms in o.material_slots:
                            if ms.material is None: ms.material = bpy.data.materials.new("c")
                            if wire(ms.material, img): done_f = True
            if done_f: by_fb += 1
            else:
                # 붙지 않은 이유가 '이미 보유'인지 확인
                if any(has_live(m) for m in bpy.data.materials): held += 1
        after = count_textured()
        na = len(rows)
        if after < before: v, why = "REGRESSION", ""
        elif after > before: v, why = "APPLIED", ("coord" if by_coord else "fallback")
        elif before > 0: v, why = "HELD", ""
        else:
            v = "NO_TEXTURE"
            why = "NO_ALBEDO" if na == 0 else "NOT_APPLIED"
        w.writerow([sha, sp[sha], na, before, after, by_coord, by_fb, held, v, why])
    except Exception as e:
        w.writerow([sha, sp[sha], 0, 0, 0, 0, 0, 0, "IMPORT_FAIL", type(e).__name__])
    fh.flush()
fh.close()
if os.path.exists(mark): os.remove(mark)
print("PART_DONE", SH)
