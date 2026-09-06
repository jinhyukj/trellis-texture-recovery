# Phase B 결과 병합 + 판정 리포트
import csv, glob
from collections import Counter
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
HDR = ["sha256","shard_path","n_albedo","before_slots","after_slots",
       "wired_by_coord","wired_by_fallback","held","verdict","reason"]
rows = []
for f in sorted(glob.glob("/workspace/jh/phase_b/part_*.csv")):
    rows += [r for r in csv.reader(open(f)) if r]
out = f"{B}/shards/shard1_binding_verification.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(HDR); w.writerows(rows)
tot = len(rows)
v = Counter(r[8] for r in rows)
print(f"검증 mesh: {tot:,}\n")
for k, n in v.most_common(): print(f"  {k:14s} {n:7,} ({n/tot*100:5.1f}%)")
reg = [r for r in rows if r[8] == "REGRESSION"]
print(f"\n🔴 REGRESSION (있던 텍스처가 사라짐): {len(reg)}")
for r in reg[:5]: print(f"     {r[3]}→{r[4]}  {r[1]}")
nt = Counter(r[9] for r in rows if r[8] == "NO_TEXTURE")
if nt:
    print("\nNO_TEXTURE 내역:")
    for k, n in nt.most_common(): print(f"  {k:14s} {n:7,}")
ap = [r for r in rows if r[8] == "APPLIED"]
src = Counter(r[9] for r in ap)
print(f"\nAPPLIED {len(ap):,} 중 성공 경로:")
for k, n in src.most_common(): print(f"  {k:10s} {n:7,}")
c = sum(int(r[5]) for r in rows); f2 = sum(int(r[6]) for r in rows)
print(f"\n텍스처 단위 배선: 좌표 {c:,} · 폴백 {f2:,}  → Phase A 기여 {c/max(c+f2,1)*100:.0f}%")
print(f"\n저장: {out}")
