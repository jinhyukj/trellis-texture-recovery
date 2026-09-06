import csv, glob, re
from collections import defaultdict, Counter
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
def n(x): return re.sub(r"[^a-z0-9]", "", x.lower())
ALB = {"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency",
       "diffuse","diffusemap","maintexture","color","tex","base","basetex","col","diff"}
sc = {}
for f in glob.glob("/workspace/jh/slotscan/part_*.csv"):
    for r in csv.reader(open(f)):
        if r and not r[2].startswith("IMPORT"):
            sc[r[0]] = (r[1], r[2], int(r[6]))
phasea = set(s for s, (g, v, _) in sc.items() if not (g == "HAS_SLOT" and v == "FIT"))
tex = defaultdict(set)
with open(f"{B}/shards/shard1_confirmed_map.csv") as f:
    for r in csv.DictReader(f):
        if r["downloaded"] == "1" and n(r["tex_slot"]) in ALB:
            tex[r["sha256"]].add(r["texture_path"])
c = Counter()
for s in phasea:
    nt = len(tex.get(s, ()))
    nm = sc[s][2]
    if nt <= 1: c["A. 텍스처 1장 - 어디 붙여도 동일"] += 1
    elif nm <= 1: c["B. 재질 1개 - 전부 같은 곳"] += 1
    else: c["C. 재질/텍스처 다수 - 좌표 진짜 필요"] += 1
tot = len(phasea)
print(f"Phase A 대상 {tot}건의 실제 난이도:")
for k, v in c.most_common():
    print(f"  {k:36s} {v:5d} ({v/tot*100:.0f}%)")
