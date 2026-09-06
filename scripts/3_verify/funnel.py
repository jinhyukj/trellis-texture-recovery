import csv, re
from collections import Counter, defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"

# ① shard1 전체 텍스처 상태
st = Counter()
with open(f"{B}/shards/shard1_texture_status_v2.csv") as f:
    for r in csv.DictReader(f): st[r["tex_status"]] += 1
tot = sum(st.values())
print(f"[1] shard1 전체 mesh: {tot:,}")
for k, v in st.most_common(): print(f"      {k:22s} {v:7,}")

BK = {"TEX_MISSING","NO_REF_OR_EMBEDDED","TEX_PARTIAL","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"}
prob = sum(v for k, v in st.items() if k in BK)
print(f"\n[2] 텍스처 문제 5버킷 합계: {prob:,}")

# ② 회수 시도 대상 (Unity 아님 제외)
res = Counter(); shas = set()
with open(f"{B}/shards/shard1_confirmed_results.csv") as f:
    for r in csv.DictReader(f):
        res[r["result"]] += 1; shas.add(r["sha256"])
att = sum(res.values())
print(f"[3] 회수 시도 대상 (NO_UNITY repo 제외): {att:,}  ← 제외분 {prob-att:,}")

conf = sum(v for k, v in res.items() if k.endswith("_CONFIRMED"))
col = sum(v for k, v in res.items() if k.endswith("_COLORS_ONLY"))
print(f"\n[4] 결과")
print(f"      확정 + 텍스처 확보   {conf:7,}  ({conf/att*100:.1f}%)")
print(f"      확정 + 단색(정상)    {col:7,}  ({col/att*100:.1f}%)")
for k, v in res.most_common():
    if not (k.endswith("_CONFIRMED") or k.endswith("_COLORS_ONLY")):
        print(f"      {k:20s} {v:7,}")

# ③ 실제 확보 텍스처
files = 0; tex = set()
with open(f"{B}/shards/shard1_confirmed_files.csv") as f:
    for r in csv.DictReader(f): files += 1
def n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}
alb = set(); anym = set()
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] != "1": continue
        anym.add(r["sha256"])
        if n(r["tex_slot"]) in ALB: alb.add(r["sha256"])
print(f"\n[5] 실제 확보")
print(f"      텍스처 파일           {files:7,} 개")
print(f"      텍스처 받은 mesh      {len(anym):7,}")
print(f"      그중 albedo 있는 mesh {len(alb):7,}   ← A 논의의 모수")
