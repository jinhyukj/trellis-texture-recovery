# shard1 표본 텍스처 감사: 포맷별 텍스처 보유/참조해석/부재 분류
import os, re, json, struct, random
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
SH=f"{B}/shards/shard1"
df=pd.read_csv(f"{SH}.csv")
random.seed(42)
sample=df.sample(min(4000,len(df)), random_state=42)
TEXRE=re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)
def audit(rel):
    p=os.path.join(SH,rel); ext=rel.rsplit(".",1)[-1].lower() if "." in rel else ""
    dp=os.path.dirname(p)
    try:
        if not os.path.exists(p): return ("GONE_FILE",ext)
        if ext in ("stl","ply"): return ("NO_TEX_BY_FORMAT",ext)
        data=open(p,"rb").read()
        if ext=="glb":
            if data[:4]==b"glTF":
                jl=struct.unpack("<I",data[12:16])[0]; g=json.loads(data[20:20+jl])
            else: g=json.loads(data.decode("utf8","ignore"))
            imgs=g.get("images",[])
            if not imgs: return ("NO_TEX_BY_DESIGN",ext)
            ext_uris=[i.get("uri","") for i in imgs if i.get("uri") and not i["uri"].startswith("data:")]
            if not ext_uris: return ("TEX_EMBEDDED",ext)
            import urllib.parse
            ok=all(os.path.exists(os.path.normpath(os.path.join(dp,urllib.parse.unquote(u.replace("\\","/"))))) for u in ext_uris)
            return ("TEX_RESOLVED" if ok else "TEX_MISSING",ext)
        if ext=="gltf":
            g=json.loads(data.decode("utf8","ignore"))
            imgs=[i.get("uri","") for i in g.get("images",[]) if i.get("uri") and not i["uri"].startswith("data:")]
            if not imgs:
                return ("TEX_EMBEDDED" if g.get("images") else "NO_TEX_BY_DESIGN",ext)
            import urllib.parse
            ok=all(os.path.exists(os.path.normpath(os.path.join(dp,urllib.parse.unquote(u.replace("\\","/"))))) for u in imgs)
            return ("TEX_RESOLVED" if ok else "TEX_MISSING",ext)
        if ext=="obj":
            txt=data.decode("utf8","ignore")
            mtls=[m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$", txt)]
            if not mtls: return ("NO_TEX_BY_DESIGN",ext)
            fs=set(x.lower() for x in os.listdir(dp))
            mfound=[m for m in mtls if os.path.basename(m).lower() in fs]
            if not mfound: return ("TEX_MISSING",ext)  # mtl 자체가 없음
            texs=[]
            for m in mfound:
                mt=open(os.path.join(dp,[x for x in os.listdir(dp) if x.lower()==os.path.basename(m).lower()][0]),"rb").read().decode("utf8","ignore")
                texs += [t.strip().split()[-1] for t in re.findall(r"(?im)^map_\w+\s+(.+)$", mt)]
            if not texs: return ("NO_TEX_BY_DESIGN",ext)  # mtl은 있는데 map 없음(단색 재질)
            ok=any(os.path.basename(t).lower() in fs for t in texs)
            return ("TEX_RESOLVED" if ok else "TEX_MISSING",ext)
        if ext in ("fbx","blend","dae"):
            refs=set(os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore").lower() for m in TEXRE.findall(data))
            if not refs: return ("NO_REF_OR_EMBEDDED",ext)
            # repo 폴더 전체에서 존재 확인
            repo_root=os.path.join(SH, rel.split("/")[0])
            have=set()
            for dp2,_,fs2 in os.walk(repo_root):
                for f2 in fs2: have.add(f2.lower())
            ok=any(r in have for r in refs)
            return ("TEX_RESOLVED" if ok else "TEX_MISSING",ext)
        return ("OTHER",ext)
    except Exception:
        return ("ERR",ext)
with Pool(24) as p:
    rs=p.map(audit, sample.shard_path.tolist(), chunksize=32)
from collections import Counter
c=Counter(r[0] for r in rs)
print(f"표본 {len(rs)}개 분류:")
for k,v in c.most_common(): print(f"  {k:18s} {v:5d} ({v/len(rs)*100:.1f}%)")
print("\nTEX_MISSING 포맷 분포:", dict(Counter(e for s,e in rs if s=="TEX_MISSING")))
