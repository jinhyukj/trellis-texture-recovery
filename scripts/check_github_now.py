# 이 시점까지 추출된 github mesh 전수: sha256 대조 (+glb 구조·mesh)
import os, sys, hashlib, json, struct
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
md=pd.read_csv(f"{B}/metadata.csv", usecols=["sha256","file_identifier"])
p=md.file_identifier.str.split("/")
md=md.assign(rel="raw/github/extracted/"+p.str[3]+"/"+p.str[4]+"/"+p.str[7:].str.join("/"))
rows=[(r.sha256, os.path.join(B,r.rel)) for r in md.itertuples() if os.path.exists(os.path.join(B,r.rel))]
print(f"검사 대상(현재 추출된 mesh): {len(rows):,}", flush=True)
def check(t):
    sha, path = t
    try:
        data=open(path,"rb").read()
        if hashlib.sha256(data).hexdigest()!=sha: return ("SHA_MISMATCH",path)
        if path.lower().endswith(".glb"):
            if len(data)<20 or data[:4]!=b"glTF": return ("BAD_MAGIC",path)
            ln=struct.unpack("<I",data[8:12])[0]
            if ln!=len(data): return ("LEN_MISMATCH",path)
            jl=struct.unpack("<I",data[12:16])[0]
            g=json.loads(data[20:20+jl])
            ms=g.get("meshes",[])
            if not ms or not any("POSITION" in pr.get("attributes",{}) for m in ms for pr in m.get("primitives",[])):
                return ("NO_MESH",path)
        return None
    except Exception as e:
        return (f"ERR_{type(e).__name__}",path)
with Pool(16) as pool:
    bad=[r for r in pool.map(check, rows, chunksize=64) if r]
from collections import Counter
print(f"문제: {len(bad)}개  {dict(Counter(b[0] for b in bad))}")
for b in bad[:8]: print("  ", b[0], b[1].split("extracted/")[-1][:90])
