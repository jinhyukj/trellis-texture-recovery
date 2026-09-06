# TEX_MISSING Unity mesh 표본: repo의 .mat/.meta 체인으로 텍스처가 확정 연결되는지 검증
import os, re, subprocess, shutil, sys
import pandas as pd
ST="/workspace/jh/shard1_texture_status.csv"
META="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/metadata.csv"
TMP="/workspace/jh/unity_tmp"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
env=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
df=pd.read_csv(ST); md=pd.read_csv(META)
fid=dict(zip(md.sha256, md.file_identifier))
s=df[(df.tex_status=="TEX_MISSING") & df.shard_path.str.contains("/Assets/") & df.ext.isin(["fbx","obj","blend","dae"])].sample(20, random_state=11)
ok=fail=0; results=[]
for _,r in s.iterrows():
    f=str(fid.get(r.sha256,""))
    if "github.com" not in f: continue
    parts=f.split("github.com/")[1].split("/"); org,repo,commit=parts[0],parts[1],parts[3]
    inner="/".join(parts[4:]); mdir=os.path.dirname(inner)
    rd=os.path.join(TMP,f"{org}__{repo}")
    try:
        if not os.path.exists(rd):
            subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],env=env,timeout=240,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.mat","*.meta"],env=env,timeout=120,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(["git","-C",rd,"checkout","--quiet",commit],env=env,timeout=600,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        ls=subprocess.run(["git","-C",rd,"-c","core.quotepath=false","ls-tree","-r","--name-only",commit],capture_output=True,text=True,timeout=120,env=env).stdout.splitlines()
        tree=set(ls)
        # guid → 실제 파일 경로 맵 (.meta 파싱)
        g2p={}
        for dp,_,fs in os.walk(rd):
            for fn in fs:
                if fn.endswith(".meta"):
                    p=os.path.join(dp,fn)
                    try: t=open(p,encoding="utf8",errors="ignore").read(4096)
                    except: continue
                    m=re.search(r"guid:\s*([0-9a-f]{32})",t)
                    if m: g2p[m.group(1)]=os.path.relpath(p,rd)[:-5]
        # mesh 폴더 근처(같은 dir → 상위 dir 순)의 .mat에서 텍스처 guid 추출
        cands=[]
        for dp,_,fs in os.walk(rd):
            for fn in fs:
                if fn.endswith(".mat"):
                    rel=os.path.relpath(os.path.join(dp,fn),rd)
                    near = rel.startswith(mdir+"/") or os.path.dirname(rel)==mdir or os.path.dirname(os.path.dirname(rel))==os.path.dirname(mdir)
                    t=open(os.path.join(dp,fn),encoding="utf8",errors="ignore").read()
                    for g in re.findall(r"guid:\s*([0-9a-f]{32})",t):
                        p=g2p.get(g,"")
                        if p.lower().endswith(IMG) and p in tree: cands.append((rel,p,near))
        near_hits=[c for c in cands if c[2]]
        verdict = "CHAIN_OK_NEAR" if near_hits else ("CHAIN_OK_FAR" if cands else "NO_CHAIN")
        results.append((r.sha256, inner, verdict, len(near_hits), len(cands)))
        ok+=1
    except Exception as e:
        results.append((r.sha256, inner, f"CLONE_FAIL:{type(e).__name__}",0,0)); fail+=1
    sys.stdout.write("."); sys.stdout.flush()
shutil.rmtree(TMP, ignore_errors=True)
print()
from collections import Counter
c=Counter(v for _,_,v,_,_ in results)
print("Unity 체인 검증 (TEX_MISSING 표본):")
for k,v in c.most_common(): print(f"  {k:16s} {v}")
for r in results[:20]: print("   ", r[2], "near", r[3], "all", r[4], "|", r[1][:70])
