# TEX_RESOLVED/TEX_MISSING 전수: 참조별 found/missing 계수 → TEX_PARTIAL 분리
import os, re, json, struct, csv, urllib.parse
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
SH=f"{B}/shards/shard1"
df=pd.read_csv(f"{B}/shards/shard1_texture_status.csv")
tgt=df[df.tex_status.isin(["TEX_RESOLVED","TEX_MISSING"])]
TEXRE=re.compile(rb"[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)", re.I)
_rc={}
def repo_files(root):
    if root not in _rc:
        have=set()
        for dp,_,fs in os.walk(root):
            for f in fs: have.add(f.lower())
        _rc[root]=have
        if len(_rc)>64: _rc.pop(next(iter(_rc)))
    return _rc[root]
def audit(row):
    sha,rel,ext,old=row
    p=os.path.join(SH,rel); dp=os.path.dirname(p)
    try:
        data=open(p,"rb").read()
        found=[]; miss=[]
        if ext in ("glb","gltf"):
            if ext=="glb" and data[:4]==b"glTF":
                jl=struct.unpack("<I",data[12:16])[0]; g=json.loads(data[20:20+jl])
            else: g=json.loads(data.decode("utf8","ignore"))
            uris=[i.get("uri","") for i in g.get("images",[]) if i.get("uri") and not i["uri"].startswith("data:")]
            for u in uris:
                q=os.path.normpath(os.path.join(dp,urllib.parse.unquote(u.replace("\\","/"))))
                (found if os.path.exists(q) else miss).append(os.path.basename(u))
        elif ext=="obj":
            txt=data.decode("utf8","ignore")
            fs=set(x.lower() for x in os.listdir(dp))
            for m in [m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$",txt)]:
                if os.path.basename(m).lower() not in fs: miss.append(os.path.basename(m)); continue
                real=[x for x in os.listdir(dp) if x.lower()==os.path.basename(m).lower()][0]
                mt=open(os.path.join(dp,real),"rb").read().decode("utf8","ignore")
                for t in re.findall(r"(?im)^map_\w+\s+(.+)$",mt):
                    bn=os.path.basename(t.strip().split()[-1])
                    (found if bn.lower() in fs else miss).append(bn)
        elif ext in ("fbx","blend","dae"):
            have=repo_files(os.path.join(SH,rel.split("/")[0]))
            refs=sorted(set(os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore") for m in TEXRE.findall(data)))
            for r2 in refs: (found if r2.lower() in have else miss).append(r2)
        else:
            return (sha,rel,ext,old,0,0,"")
        nf,nm=len(found),len(miss)
        st = "TEX_RESOLVED" if nm==0 and nf>0 else ("TEX_MISSING" if nf==0 and nm>0 else ("TEX_PARTIAL" if nf>0 and nm>0 else old))
        return (sha,rel,ext,st,nf,nm,";".join(miss[:6]))
    except Exception as e:
        return (sha,rel,ext,"ERR",0,0,type(e).__name__)
rows=[(r.sha256,r.shard_path,r.ext,r.tex_status) for r in tgt.itertuples(index=False)]
rows.sort(key=lambda r:r[1].split("/")[0])
with Pool(16) as p:
    rs=p.map(audit, rows, chunksize=64)
out=pd.DataFrame(rs,columns=["sha256","shard_path","ext","tex_status2","n_ref_found","n_ref_missing","missing_sample"])
out.to_csv("/workspace/jh/partial_audit.csv",index=False)
from collections import Counter
print(Counter(out.tex_status2).most_common())
pt=out[out.tex_status2=="TEX_PARTIAL"]
print("\nTEX_PARTIAL:",len(pt),"| 포맷:",dict(Counter(pt.ext)))
print(pt.head(5).to_string())
