# URL-인코딩 URI로 끊긴 gltf 참조를 raw에서 사후 회수 (pinned commit)
import os, json, urllib.parse, urllib.request, time
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"; EX=f"{B}/raw/github/extracted"
md=pd.read_csv(f"{B}/metadata.csv", usecols=["file_identifier"])
commit_of={}
for f in md.file_identifier:
    p=f.split("/")
    if len(p)>=8: commit_of[(p[3],p[4])]=p[6]
jobs=[]
for dp,_,fs in os.walk(EX):
    for f in fs:
        if not f.lower().endswith(".gltf"): continue
        p=os.path.join(dp,f)
        try: g=json.loads(open(p,"rb").read())
        except Exception: continue
        for it in g.get("buffers",[])+g.get("images",[]):
            u=it.get("uri","")
            if not u or u.startswith("data:"): continue
            dec=urllib.parse.unquote(u.replace("\\","/"))
            dst=os.path.normpath(os.path.join(dp,dec))
            if os.path.exists(dst) or os.path.exists(os.path.normpath(os.path.join(dp,u))): continue
            rel=os.path.relpath(p,EX).split("/"); org,repo=rel[0],rel[1]
            c=commit_of.get((org,repo))
            if not c: continue
            inner_dir=os.path.dirname("/".join(rel[2:]))
            remote=os.path.normpath(os.path.join(inner_dir,dec)).replace("\\","/")
            jobs.append((org,repo,c,remote,dst))
print(f"회수 대상 참조: {len(jobs)}")
def fetch(j):
    org,repo,c,remote,dst=j
    url=f"https://raw.githubusercontent.com/{org}/{repo}/{c}/{urllib.parse.quote(remote)}"
    try:
        data=urllib.request.urlopen(url,timeout=60).read()
        os.makedirs(os.path.dirname(dst),exist_ok=True)
        t=dst+".copytmp"; open(t,"wb").write(data); os.replace(t,dst); return 1
    except Exception: return 0
with Pool(8) as pool: rs=pool.map(fetch,jobs)
print(f"회수 성공 {sum(rs)} / 실패 {len(rs)-sum(rs)} (실패=원천에도 없음)")
