# 67% 그룹: 장부의 slot_index 가 실제 임포트된 재질 슬롯 범위와 맞는지 실측
# usage: blender -b --factory-startup -noaudio -P slotcheck.py -- <N>
import bpy, os, sys, re, csv, random
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
N = int(sys.argv[sys.argv.index("--")+1])
def n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}

per = defaultdict(list); sp = {}
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1" or n(r["tex_slot"]) not in ALB: continue
        per[r["sha256"]].append((r["slot_index"], r["mat_path"]))
        sp[r["sha256"]] = r["shard_path"]
ok = []
for sha, rows in per.items():
    slots = [s for s, _ in rows]; mats = set(m for _, m in rows)
    if all(s == "" for s in slots): continue
    if len(set(slots)) < len(mats): continue
    ok.append(sha)
random.seed(11); random.shuffle(ok)

tally = {"FIT": 0, "OVERFLOW": 0, "NO_SLOTS": 0, "SKIP": 0}
done = 0
for sha in ok:
    if done >= N: break
    p = os.path.join(B, "shards/shard1", sp[sha])
    if not os.path.exists(p): tally["SKIP"] += 1; continue
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        lo = p.lower()
        if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=p)
        elif lo.endswith(".obj"):
            try: bpy.ops.wm.obj_import(filepath=p)
            except AttributeError: bpy.ops.import_scene.obj(filepath=p)
        elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=p)
        else: tally["SKIP"] += 1; continue
    except Exception:
        tally["SKIP"] += 1; continue
    maxslot = max(int(s) for s, _ in per[sha] if s != "")
    counts = [len(o.material_slots) for o in bpy.data.objects if o.type == "MESH"]
    if not counts or max(counts) == 0:
        tally["NO_SLOTS"] += 1; k = "NO_SLOTS"
    elif maxslot < max(counts):
        tally["FIT"] += 1; k = "FIT"
    else:
        tally["OVERFLOW"] += 1; k = "OVERFLOW"
    done += 1
    print(f"{k:9s} 장부최대슬롯={maxslot} 임포트슬롯수={counts[:4]} {os.path.basename(sp[sha])}", flush=True)
print("TALLY", tally)
