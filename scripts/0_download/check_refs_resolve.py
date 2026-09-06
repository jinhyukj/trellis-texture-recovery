# 파일 내부 참조를 "적힌 경로 그대로" 해석해 실제로 열리는지 전수 확인 (gltf·obj)
import os, re, json, urllib.parse
from multiprocessing import Pool
EX="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/raw/github/extracted"
files=[]
for dp,_,fs in os.walk(EX):
    for f in fs:
        if f.lower().endswith((".gltf",".obj")): files.append(os.path.join(dp,f))
print(f"검사 대상: gltf/obj {len(files):,}개", flush=True)
def resolve(base, uri):
    u=urllib.parse.unquote(uri.strip().replace("\\","/"))
    return os.path.normpath(os.path.join(os.path.dirname(base), u))
def check(p):
    ok=miss=0; missing=[]
    try:
        if p.lower().endswith(".gltf"):
            g=json.loads(open(p,"rb").read())
            uris=[b.get("uri","") for b in g.get("buffers",[])+g.get("images",[]) if b.get("uri") and not b["uri"].startswith("data:")]
        else:
            txt=open(p,"rb").read().decode("utf8","ignore")
            uris=[m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$", txt)]
        for u in uris:
            if os.path.exists(resolve(p,u)): ok+=1
            else: miss+=1; missing.append(u)
    except Exception:
        return (0,0,[])
    return (ok,miss,[(p,m) for m in missing[:1]])
with Pool(16) as pool:
    rs=pool.map(check, files, chunksize=64)
ok=sum(r[0] for r in rs); miss=sum(r[1] for r in rs)
ex=[e for r in rs for e in r[2]][:6]
print(f"내부 참조 총 {ok+miss:,}건 — 경로 그대로 열림 {ok:,} ({ok/(ok+miss)*100:.1f}%) / 끊김 {miss:,}")
for p,m in ex: print("  끊김 예:", p.split("extracted/")[-1][:70], "→", m[:40])
