import os, sys
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0,"/workspace/jh")
from check_glbs import check
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_sketchfab"
led=pd.read_csv(f"{B}/raw/metadata.csv")
targets=[("sketchfab_r0",sha,os.path.join(B,lp)) for sha,lp in zip(led.sha256,led.local_path)]
print(f"검사 대상(장부 기준): {len(targets)}")
with Pool(32) as p:
    results=p.map(check,targets,chunksize=64)
bad=[r for r in results if r["err"]]
from collections import Counter
print(f"결과: {len(results)}개 검사, 문제 {len(bad)}개  {dict(Counter(r['err'].split('(')[0] for r in bad))}")
for r in bad[:10]: print(" ",r["err"],r["path"])
