import os, sys, json, struct, hashlib
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0,"/workspace/jh")
from check_glbs import check   # 동일 검사 함수 재사용
B="/workspace/jh/trellis500k/datasets/ABO"
led=pd.read_csv(f"{B}/raw/metadata.csv")
targets=[("ABO",sha,os.path.join(B,lp)) for sha,lp in zip(led.sha256,led.local_path)]
print(f"검사 대상: {len(targets)}")
with Pool(32) as p:
    results=p.map(check,targets,chunksize=32)
bad=[r for r in results if r["err"]]
from collections import Counter
print(f"ABO: {len(results)}개 검사, 문제 {len(bad)}개  {dict(Counter(r['err'].split('(')[0] for r in bad))}")
for r in bad[:10]: print(" ",r["err"],r["path"])
