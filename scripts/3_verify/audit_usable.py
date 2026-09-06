# 최종 통과분(APPLIED/HELD) 중 "사실상 약한" 케이스 집계 — 변경 없음, 분석만
import csv, sys
from collections import Counter
SHARD = sys.argv[1] if len(sys.argv) > 1 else "shard2"
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
rows = list(csv.DictReader(open(f"{B}/shards/{SHARD}_binding_verification.csv")))
use = [r for r in rows if r["verdict"] in ("APPLIED", "HELD")]
ap = [r for r in use if r["verdict"] == "APPLIED"]
hd = [r for r in use if r["verdict"] == "HELD"]

def f(x, d=0.0):
    try: return float(x)
    except Exception: return d
def i(x, d=0):
    try: return int(x)
    except Exception: return d

print("="*58)
print(f"[{SHARD}] 최종 통과 {len(use):,} 의 품질 내역")
print("="*58)
print(f"  APPLIED {len(ap):,} · HELD {len(hd):,}\n")

# ① APPLIED의 albedo 커버리지 (배선된 텍스처 수 / 확정 albedo 수)
cov = Counter()
for r in ap:
    n = i(r["n_albedo"]); w = i(r["wired_by_coord"]) + i(r["wired_by_fallback"])
    if n == 0: cov["albedo 0 (normal/AO만)"] += 1
    elif w >= n: cov["전량 배선"] += 1
    elif w / n >= 0.5: cov["절반 이상"] += 1
    elif w > 0: cov["절반 미만 ⚠️"] += 1
    else: cov["0장 배선 ⚠️⚠️"] += 1
print("① APPLIED의 albedo 배선 커버리지")
for k, v in cov.most_common(): print(f"   {k:22s} {v:6,} ({v/len(ap)*100:4.1f}%)")

# ② 렌더 변화가 미미한 것
bands = Counter()
for r in ap:
    d = f(r["render_diff"])
    bands["거의 없음 (<0.01) ⚠️" if d < 0.01 else ("작음 (0.01~0.05)" if d < 0.05 else "뚜렷 (≥0.05)")] += 1
print("\n② APPLIED의 렌더 변화량")
for k in ("뚜렷 (≥0.05)", "작음 (0.01~0.05)", "거의 없음 (<0.01) ⚠️"):
    if bands.get(k): print(f"   {k:22s} {bands[k]:6,} ({bands[k]/len(ap)*100:4.1f}%)")

# ③ HELD: 우리가 기여한 게 있나
h = Counter()
for r in hd:
    n = i(r["n_albedo"]); w = i(r["wired_by_coord"]) + i(r["wired_by_fallback"])
    h["기존 텍스처만 (우리 기여 0)" if w == 0 else "일부 슬롯 추가 배선"] += 1
print("\n③ HELD 내역")
for k, v in h.most_common(): print(f"   {k:26s} {v:6,} ({v/max(len(hd),1)*100:4.1f}%)")

# ④ 종합: 엄격 기준으로 걸러낼 규모
weak = [r for r in ap
        if (i(r["wired_by_coord"]) + i(r["wired_by_fallback"])) == 0
        or f(r["render_diff"]) < 0.01
        or (i(r["n_albedo"]) > 0 and (i(r["wired_by_coord"]) + i(r["wired_by_fallback"])) / i(r["n_albedo"]) < 0.5)]
strict = [r for r in ap if r not in weak]
print("\n" + "="*58)
print("④ 엄격 기준 적용 시")
print(f"   현재 통과            {len(use):,}")
print(f"   ├─ 견고 (APPLIED)     {len(strict):,}")
print(f"   ├─ 약함 (APPLIED)     {len(weak):,}   ← 배선 0장·부분·렌더변화 미미")
print(f"   └─ HELD (원래 정상)   {len(hd):,}")
print(f"\n   → 엄격 기준 사용 가능: {len(strict)+len(hd):,} ({(len(strict)+len(hd))/len(use)*100:.1f}%)")
