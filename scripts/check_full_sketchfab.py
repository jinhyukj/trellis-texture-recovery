# 장부 전체 검사: 누락/sha256/GLB구조/mesh → bad 목록 파일 기록. exit 0=clean, 1=bad 존재
import os, sys
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0,"/workspace/jh")
from check_glbs import check
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_sketchfab"
led=pd.read_csv(f"{B}/raw/metadata.csv")
targets=[("sk",sha,os.path.join(B,lp)) for sha,lp in zip(led.sha256,led.local_path)]
print(f"검사: {len(targets)}개")
with Pool(32) as p: results=p.map(check,targets,chunksize=64)
bad=[r for r in results if r["err"]]
with open("/workspace/jh/sk_bad.txt","w") as f:
    for r in bad: f.write(f"{r['err']}\t{r['path']}\n")
from collections import Counter
print(f"문제 {len(bad)}개 {dict(Counter(r['err'].split('(')[0] for r in bad))}")
sys.exit(1 if bad else 0)
