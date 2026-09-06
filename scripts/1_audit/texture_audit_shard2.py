# shard2 전수 텍스처 감사 → per-mesh CSV (sha256, path, ext, status, missing_refs)
import os, re, json, struct, csv, sys, urllib.parse
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
SH=f"{B}/shards/shard2"
OUT="/workspace/jh/shard2_texture_status.csv"
df=pd.read_csv(f"{SH}.csv")
TEXRE=re.compile(rb"[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)", re.I)
_repo_cache={}
def repo_files(root):
    if root not in _repo_cache:
        have=set()
        for dp,_,fs in os.walk(root):
            for f in fs: have.add(f.lower())
        _repo_cache[root]=have
        if len(_repo_cache)>64: _repo_cache.pop(next(iter(_repo_cache)))
    return _repo_cache[root]
def audit(row):
    sha,rel=row
    p=os.path.join(SH,rel); ext=rel.rsplit(".",1)[-1].lower() if "." in rel else ""
    dp=os.path.dirname(p); miss=[]
    try:
        if not os.path.exists(p): return (sha,rel,ext,"GONE_FILE","")
        if ext in ("stl","ply"): return (sha,rel,ext,"NO_TEX_BY_FORMAT","")
        data=open(p,"rb").read()
        if ext=="glb":
            if data[:4]==b"glTF":
                jl=struct.unpack("<I",data[12:16])[0]; g=json.loads(data[20:20+jl])
            else: g=json.loads(data.decode("utf8","ignore"))
            imgs=g.get("images",[])
            if not imgs: return (sha,rel,ext,"NO_TEX_BY_DESIGN","")
            uris=[i.get("uri","") for i in imgs if i.get("uri") and not i["uri"].startswith("data:")]
            if not uris: return (sha,rel,ext,"TEX_EMBEDDED","")
            miss=[u for u in uris if not os.path.exists(os.path.normpath(os.path.join(dp,urllib.parse.unquote(u.replace("\\","/")))))]
            return (sha,rel,ext,"TEX_RESOLVED" if not miss else "TEX_MISSING",";".join(os.path.basename(m) for m in miss[:8]))
        if ext=="gltf":
            g=json.loads(data.decode("utf8","ignore"))
            allimgs=g.get("images",[])
            uris=[i.get("uri","") for i in allimgs if i.get("uri") and not i["uri"].startswith("data:")]
            if not uris: return (sha,rel,ext,"TEX_EMBEDDED" if allimgs else "NO_TEX_BY_DESIGN","")
            miss=[u for u in uris if not os.path.exists(os.path.normpath(os.path.join(dp,urllib.parse.unquote(u.replace("\\","/")))))]
            return (sha,rel,ext,"TEX_RESOLVED" if not miss else "TEX_MISSING",";".join(os.path.basename(m) for m in miss[:8]))
        if ext=="obj":
            txt=data.decode("utf8","ignore")
            mtls=[m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$", txt)]
            if not mtls: return (sha,rel,ext,"NO_TEX_BY_DESIGN","")
            fs=set(x.lower() for x in os.listdir(dp))
            mfound=[m for m in mtls if os.path.basename(m).lower() in fs]
            if not mfound: return (sha,rel,ext,"TEX_MISSING",";".join(os.path.basename(m) for m in mtls[:8]))
            texs=[]
            for m in mfound:
                real=[x for x in os.listdir(dp) if x.lower()==os.path.basename(m).lower()][0]
                mt=open(os.path.join(dp,real),"rb").read().decode("utf8","ignore")
                texs += [t.strip().split()[-1] for t in re.findall(r"(?im)^map_\w+\s+(.+)$", mt)]
            if not texs: return (sha,rel,ext,"NO_TEX_BY_DESIGN","")
            found=[t for t in texs if os.path.basename(t).lower() in fs]
            if found: return (sha,rel,ext,"TEX_RESOLVED","")
            return (sha,rel,ext,"TEX_MISSING",";".join(sorted(set(os.path.basename(t) for t in texs))[:8]))
        if ext in ("fbx","blend","dae"):
            refs=sorted(set(os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore").lower() for m in TEXRE.findall(data)))
            if not refs: return (sha,rel,ext,"NO_REF_OR_EMBEDDED","")
            have=repo_files(os.path.join(SH, rel.split("/")[0]))
            if any(r in have for r in refs): return (sha,rel,ext,"TEX_RESOLVED","")
            return (sha,rel,ext,"TEX_MISSING",";".join(refs[:8]))
        return (sha,rel,ext,"OTHER","")
    except Exception as e:
        return (sha,rel,ext,"ERR",type(e).__name__)
rows=list(df.itertuples(index=False,name=None))
# repo 단위 정렬로 캐시 적중률 확보
rows.sort(key=lambda r: r[1].split("/")[0])
with Pool(32) as pool, open(OUT,"w",newline="") as f:
    w=csv.writer(f); w.writerow(["sha256","shard_path","ext","tex_status","missing_refs"])
    n=0
    for r in pool.imap(audit, rows, chunksize=64):
        w.writerow(r); n+=1
        if n%10000==0: print(f"{n}/{len(rows)}", flush=True)
from collections import Counter
sub=pd.read_csv(OUT)
c=Counter(sub.tex_status)
print(f"\n전수 {len(sub)}개 분류:")
for k,v in c.most_common(): print(f"  {k:18s} {v:6d} ({v/len(sub)*100:.1f}%)")
print("\nTEX_MISSING 포맷 분포:", dict(Counter(sub[sub.tex_status=="TEX_MISSING"].ext)))
