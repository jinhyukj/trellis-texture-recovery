# TEX_MISSING/NO_REF 버킷의 fbx/blend/dae 내부에 실제 이미지 데이터(매직바이트) 존재 여부 스캔
import os
from multiprocessing import Pool
import pandas as pd
SH="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/shards/shard1"
df=pd.read_csv("/workspace/jh/shard1_texture_status.csv")
tgt=df[df.tex_status.isin(["TEX_MISSING","NO_REF_OR_EMBEDDED"]) & df.ext.isin(["fbx","blend","dae"])]
MAGICS=[b"\x89PNG\r\n", b"\xff\xd8\xff", b"DDS |", b"II*\x00", b"MM\x00*"]  # png/jpeg/dds/tiff
def scan(row):
    sha,rel,ext,st=row
    try:
        data=open(os.path.join(SH,rel),"rb").read()
        n=sum(data.count(m) for m in MAGICS)
        return (sha,st,ext,n)
    except Exception:
        return (sha,st,ext,-1)
rows=tgt[["sha256","shard_path","ext","tex_status"]].itertuples(index=False,name=None)
with Pool(32) as p: rs=p.map(scan, list(rows), chunksize=64)
r=pd.DataFrame(rs, columns=["sha256","tex_status","ext","img_count"])
r.to_csv("/workspace/jh/embed_scan.csv", index=False)
for st in ["TEX_MISSING","NO_REF_OR_EMBEDDED"]:
    s=r[r.tex_status==st]
    print(f"\n{st} ({len(s)}) 중 내장 이미지 데이터:")
    for e in sorted(s.ext.unique()):
        se=s[s.ext==e]
        # 임계 2개 이상: 썸네일 1장 오탐 배제
        emb=(se.img_count>=2).sum(); one=(se.img_count==1).sum()
        print(f"  {e:6s} 전체 {len(se):6d} | 내장확실(>=2) {emb:6d} | 1개(썸네일?) {one:5d} | 없음 {(se.img_count==0).sum():6d}")
