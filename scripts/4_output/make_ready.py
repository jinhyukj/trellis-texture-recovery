# B 판정 통과분만 모은 최종 매핑 표 (재영님 전달용)
# 조인: verification(판정) × map(텍스처·슬롯) × coords(이름 좌표)
import csv, re
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OK = {"APPLIED", "HELD"}          # 통과 기준 (필요시 조정)

ver = {}
with open(f"{B}/shards/shard1_binding_verification.csv") as f:
    for r in csv.DictReader(f): ver[r["sha256"]] = r
co = defaultdict(list)
with open(f"{B}/shards/shard1_binding_coords.csv") as f:
    for r in csv.DictReader(f):
        if r["coord_type"] in ("GO", "FBXMAT"): co[(r["sha256"], r["mat_path"])].append(r)

rows = []
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1": continue
        v = ver.get(r["sha256"])
        if not v or v["verdict"] not in OK: continue
        cs = co.get((r["sha256"], r["mat_path"]), [])
        fbxmat = next((c["name"] for c in cs if c["coord_type"] == "FBXMAT"), "")
        go = next((c["name"] for c in cs if c["coord_type"] == "GO"), "")
        goslot = next((c["slot_index"] for c in cs if c["coord_type"] == "GO"), "")
        rows.append([
            r["sha256"], r["shard_path"], r["repo"],
            r["texture_path"], r["tex_slot"], r["mat_path"],
            r["slot_index"] or goslot, fbxmat, go,
            r["mat_alpha"], v["verdict"],
            "coord" if int(v["wired_by_coord"]) > 0 else "fallback",
        ])
out = f"{B}/shards/shard1_appearance_ready.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["sha256", "mesh_path", "repo", "texture_path", "tex_slot", "mat_path",
                "slot_index", "fbx_material_name", "gameobject_name",
                "mat_alpha", "verdict", "wired_by"])
    w.writerows(rows)
mesh = len(set(r[0] for r in rows))
print(f"{out}\n  {len(rows):,}행 / mesh {mesh:,}")
from collections import Counter
print("  판정:", dict(Counter(r[10] for r in rows)))
print("  경로:", dict(Counter(r[11] for r in rows)))
print("  슬롯종류:", dict(Counter(r[4] for r in rows).most_common(6)))
haveco = sum(1 for r in rows if r[7] or r[8])
print(f"  이름 좌표 보유 행: {haveco:,} ({haveco/max(len(rows),1)*100:.0f}%)")
