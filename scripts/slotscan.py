# 확정 회수 mesh 전수: 배선 좌표 유효성 조사 (로컬 임포트만, 네트워크 0)
# usage: blender -b --factory-startup -noaudio -P slotscan.py -- <shard_i> <of_K>
import bpy, os, sys, re, csv
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OUT = "/workspace/jh/slotscan"
a = sys.argv[sys.argv.index("--")+1:]
SH, OF = int(a[0]), int(a[1])
def n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}

per = defaultdict(list); sp = {}
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1" or n(r["tex_slot"]) not in ALB: continue
        per[r["sha256"]].append((r["slot_index"], r["mat_path"]))
        sp[r["sha256"]] = r["shard_path"]

items = []
for sha in sorted(per):
    rows = per[sha]
    slots = [s for s, _ in rows]; mats = set(m for _, m in rows)
    if all(s == "" for s in slots): grp = "NEED_NAME"
    elif len(set(slots)) < len(mats): grp = "NEED_GO"
    else: grp = "HAS_SLOT"
    items.append((sha, grp, rows))
items = [x for i, x in enumerate(items) if i % OF == SH]

os.makedirs(OUT, exist_ok=True)
fh = open(f"{OUT}/part_{SH}.csv", "w", newline="")
w = csv.writer(fh)
for sha, grp, rows in items:
    path = os.path.join(B, "shards/shard1", sp[sha])
    verdict = ""; maxslot = -1; maxsl = 0; nobj = 0; nmat = 0; matnames = ""
    try:
        maxslot = max([int(s) for s, _ in rows if s != ""] or [-1])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        lo = path.lower()
        if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=path)
        elif lo.endswith(".obj"):
            try: bpy.ops.wm.obj_import(filepath=path)
            except AttributeError: bpy.ops.import_scene.obj(filepath=path)
        elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=path)
        elif lo.endswith(".dae"): bpy.ops.wm.collada_import(filepath=path)
        else: raise RuntimeError("fmt")
        counts = [len(o.material_slots) for o in bpy.data.objects if o.type == "MESH"]
        nobj = len(counts); maxsl = max(counts) if counts else 0
        mats = [re.sub(r"\.\d+$", "", m.name) for m in bpy.data.materials]
        nmat = len(mats); matnames = "|".join(sorted(set(mats))[:8])
        if maxsl == 0: verdict = "NO_SLOTS"
        elif maxslot < 0: verdict = "NO_SLOT_IDX"      # META 출처: 번호 자체가 없음
        elif maxslot < maxsl: verdict = "FIT"
        else: verdict = "OVERFLOW"
    except Exception as e:
        verdict = "IMPORT_FAIL:" + type(e).__name__
    w.writerow([sha, grp, verdict, maxslot, maxsl, nobj, nmat, matnames, sp[sha]])
fh.close()
print("PART_DONE", SH, len(items))
