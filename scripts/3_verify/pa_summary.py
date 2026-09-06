import csv
from collections import Counter
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
rows = list(csv.DictReader(open(f"{B}/shards/shard1_binding_coords.csv")))
c = Counter(r["coord_type"] for r in rows)
meshes = set(r["sha256"] for r in rows)
print(f"총 {len(rows):,}행 / mesh {len(meshes):,}")
for k, v in c.most_common(): print(f"  {k:16s} {v:7,}")
solved = set(r["sha256"] for r in rows if r["coord_type"] in ("GO", "FBXMAT"))
print(f"\n좌표 확보: {len(solved):,} / {len(meshes):,} ({len(solved)/len(meshes)*100:.0f}%)")
na = sum(1 for r in rows if r["name"] and not r["name"].isascii())
print(f"비ASCII 이름 행: {na:,}  (유니코드 수정 반영분)")
esc = sum(1 for r in rows if "\\u0" in r["name"])
print(f"미디코드 잔존: {esc}")
