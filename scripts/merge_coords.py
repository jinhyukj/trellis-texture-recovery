# phase_a/.done → shard1_binding_coords.csv 병합 (A 실행 중에도 스냅샷 가능)
import csv, glob
from collections import Counter
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
acc = []
for f in glob.glob("/workspace/jh/phase_a/.done/*.csv"):
    try: acc += [r for r in csv.reader(open(f)) if r]
    except Exception: pass
out = f"{B}/shards/shard1_binding_coords.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["sha256","shard_path","repo","coord_type","slot_index","name","mat_path","source_file"])
    w.writerows(acc)
c = Counter(r[3] for r in acc)
solved = set(r[0] for r in acc if r[3] in ("GO","FBXMAT"))
allm = set(r[0] for r in acc)
print(f"병합 {len(acc):,}행 / mesh {len(allm):,}")
for k, v in c.most_common(): print(f"  {k:16s} {v:7,}")
print(f"좌표 확보: {len(solved):,} / {len(allm):,} ({len(solved)/max(len(allm),1)*100:.0f}%)")
