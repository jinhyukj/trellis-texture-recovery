# Phase B v2 결과 병합 + 깔때기 리포트
import csv, glob, sys
from collections import Counter
SHARD = sys.argv[1] if len(sys.argv) > 1 else "shard2"
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
HDR = ["sha256","mesh_path","n_albedo","before_slots","after_slots","wired_by_coord",
       "wired_by_fallback","verdict","reason","render_diff","diversity_delta","flat_delta"]
rows = []
for f in sorted(glob.glob(f"/workspace/jh/phase_b_{SHARD}/part_*.csv")):
    rows += [r for r in csv.reader(open(f)) if r]
out = f"{B}/shards/{SHARD}_binding_verification.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(HDR); w.writerows(rows)

tot = len(rows); v = Counter(r[7] for r in rows)
print("="*56)
print(f"[{SHARD}] 배선 검증 — 깔때기")
print("="*56)
print(f"  검증 대상 (텍스처 회수된 mesh)   {tot:8,}")
usable = v.get("APPLIED", 0) + v.get("HELD", 0)
print(f"  ├─ ✅ 바로 사용 가능             {usable:8,} ({usable/tot*100:4.1f}%)")
print(f"  │    APPLIED {v.get('APPLIED',0):,} · HELD {v.get('HELD',0):,}")
for k in ("NO_VISUAL_EFFECT", "SUSPECT", "NO_TEXTURE", "REGRESSION", "IMPORT_FAIL", "IMPORT_CRASH"):
    if v.get(k): print(f"  ├─ {'🔴' if k=='REGRESSION' else '⚠️ '} {k:18s} {v[k]:8,} ({v[k]/tot*100:4.1f}%)")
print(f"  └─ 기타                          {tot-sum(v.values())+sum(v.values())-sum(v[k] for k in v):8,}")

reg = [r for r in rows if r[7] == "REGRESSION"]
print(f"\n🔴 REGRESSION (있던 텍스처 사라짐): {len(reg)}   ← 0이어야 정상")
for r in reg[:5]: print(f"     {r[3]}→{r[4]}  {r[1]}")

ap = [r for r in rows if r[7] == "APPLIED"]
src = Counter(r[8] for r in ap)
print(f"\nAPPLIED {len(ap):,} 성공 경로: " + " · ".join(f"{k} {n:,}" for k, n in src.most_common()))
c = sum(int(r[5]) for r in rows); f2 = sum(int(r[6]) for r in rows)
print(f"텍스처 단위 배선: 좌표 {c:,} · 폴백 {f2:,}  → 좌표 기여 {c/max(c+f2,1)*100:.0f}%")

nt = Counter(r[8] for r in rows if r[7] == "NO_TEXTURE")
if nt: print("\nNO_TEXTURE 내역: " + " · ".join(f"{k} {n:,}" for k, n in nt.most_common()))
try:
    ds = [float(r[9]) for r in rows if r[7] in ("APPLIED","NO_VISUAL_EFFECT") and r[9]]
    if ds:
        ds.sort()
        print(f"\n렌더 델타(픽셀변화) 중앙값 {ds[len(ds)//2]:.4f} · 하위10% {ds[len(ds)//10]:.4f}")
except Exception: pass
print(f"\n저장: {out}")
