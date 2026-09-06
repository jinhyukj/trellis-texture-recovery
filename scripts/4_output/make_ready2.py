# B 통과분만 모은 최종 매핑 표 (shard2: 좌표가 map에 이미 있음 → 조인 불필요)
import csv, sys, os
from collections import Counter
SHARD = sys.argv[1] if len(sys.argv) > 1 else "shard2"
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OK = {"APPLIED", "HELD"}
ver = {}
with open(f"{B}/shards/{SHARD}_binding_verification.csv") as f:
    for r in csv.DictReader(f): ver[r["sha256"]] = r
rows = []
with open(f"{B}/shards/{SHARD}_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1": continue
        v = ver.get(r["sha256"])
        if not v or v["verdict"] not in OK: continue
        rows.append([r["sha256"], r["mesh_path"], r["repo"], r["texture_path"], r["tex_slot"],
                     r["mat_path"], r["slot_index"], r["fbx_material_name"], r["gameobject_name"],
                     r["mat_alpha"], v["verdict"],
                     "coord" if int(v["wired_by_coord"]) > 0 else "fallback", v["render_diff"]])
out = f"{B}/shards/{SHARD}_appearance_ready.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["sha256","mesh_path","repo","texture_path","tex_slot","mat_path","slot_index",
                "fbx_material_name","gameobject_name","mat_alpha","verdict","wired_by","render_diff"])
    w.writerows(rows)
mesh = set(r[0] for r in rows)
print(f"{out}\n  {len(rows):,}행 / mesh {len(mesh):,}")
print("  판정:", dict(Counter(r[10] for r in rows)))
print("  경로:", dict(Counter(r[11] for r in rows)))
ext = Counter(os.path.splitext(r[1])[1].lower().lstrip(".") for r in rows if r[0] in mesh)
me = Counter()
seen = set()
for r in rows:
    if r[0] in seen: continue
    seen.add(r[0]); me[os.path.splitext(r[1])[1].lower().lstrip(".")] += 1
print("  포맷별 mesh 수:", dict(me.most_common()))
