# 정찰 A: NO_MAT mesh가 .prefab/.unity 씬에 배선돼 있는가 / B: NO_UNITY repo의 타 엔진 마커
import os, re, subprocess, shutil, random, sys, glob
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP="/workspace/jh/probe2_tmp"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
rec=pd.read_csv(f"{B}/shards/shard1_unity_recovery.csv")
md=pd.read_csv(f"{B}/metadata.csv"); fid=dict(zip(md.sha256,md.file_identifier))
random.seed(21)
def parts_of(sha):
    f=str(fid.get(sha,""))
    p=f.split("github.com/")[1].split("/")
    return p[0],p[1],p[3],"/".join(p[4:])
def probe_nomat(arg):
    sha,inner_sp=arg
    try:
        org,repo,commit,inner=parts_of(sha)
        rd=os.path.join(TMP,f"A_{org}__{repo}")
        if not os.path.exists(rd):
            subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],env=ENV,timeout=300,check=True,capture_output=True)
            subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.meta","*.mat","*.prefab","*.unity"],env=ENV,timeout=120,capture_output=True)
            subprocess.run(["git","-C",rd,"checkout","--quiet","--force",commit],env=ENV,timeout=1200,capture_output=True)
        mm=os.path.join(rd,inner+".meta")
        if not os.path.exists(mm): return "MESH_META_ABSENT"
        mg=GUID.search(open(mm,encoding="utf8",errors="ignore").read(2048))
        if not mg: return "MESH_META_NOGUID"
        mesh_guid=mg.group(1)
        g2p={}
        for mp in glob.glob(f"{rd}/**/*.meta",recursive=True):
            m=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
            if m: g2p[m.group(1)]=os.path.relpath(mp,rd)[:-5]
        hit_mats=set()
        for sf in glob.glob(f"{rd}/**/*.prefab",recursive=True)+glob.glob(f"{rd}/**/*.unity",recursive=True):
            try: txt=open(sf,encoding="utf8",errors="ignore").read()
            except: continue
            if mesh_guid not in txt: continue
            for g in GUID.findall(txt):
                p=g2p.get(g,"")
                if p.endswith(".mat"): hit_mats.add(p)
        if not hit_mats: return "NO_SCENE_REF"
        for mp in hit_mats:
            try: t=open(os.path.join(rd,mp),encoding="utf8",errors="ignore").read()
            except: continue
            for g in GUID.findall(t):
                p=g2p.get(g,"")
                if p.lower().endswith(IMG): return "PREFAB_CHAIN_OK"
        return "SCENE_REF_BUT_NO_TEX"
    except Exception as e:
        return f"ERR:{type(e).__name__}"
def probe_nouni(arg):
    sha=arg
    try:
        org,repo,commit,inner=parts_of(sha)
        rd=os.path.join(TMP,f"B_{org}__{repo}")
        if not os.path.exists(rd):
            subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],env=ENV,timeout=300,check=True,capture_output=True)
        ls=subprocess.run(["git","-C",rd,"-c","core.quotepath=false","ls-tree","-r","--name-only",commit],env=ENV,timeout=300,capture_output=True,text=True,errors="replace").stdout.lower().splitlines()
        s=set()
        if any(x.endswith((".tscn",".tres")) or x.endswith("project.godot") or x.endswith(".import") for x in ls): s.add("godot")
        if any(x.endswith(".uasset") for x in ls): s.add("unreal")
        if any(x.endswith(".vmt") for x in ls): s.add("source")
        if any(x.endswith(".mtl") for x in ls): s.add("objmtl")
        mdir=os.path.dirname(inner).lower()
        if any(x.endswith(IMG) and (os.path.dirname(x)==mdir or (mdir and x.startswith(mdir+"/"))) for x in ls): s.add("img_near_mesh")
        if any(x.endswith(IMG) for x in ls): s.add("img_in_repo")
        return "+".join(sorted(s)) if s else "none"
    except Exception as e:
        return f"ERR:{type(e).__name__}"
nm=rec[rec.result=="NO_MAT"].sample(30,random_state=21)
nu=rec[rec.result=="NO_UNITY"].sample(50,random_state=21)
with Pool(6) as p:
    ra=p.map(probe_nomat,[(r.sha256,r.shard_path) for r in nm.itertuples()])
    rb=p.map(probe_nouni,[r.sha256 for r in nu.itertuples()])
shutil.rmtree(TMP,ignore_errors=True)
from collections import Counter
print("=== A: NO_MAT 표본 30 — prefab/씬 배선 ===")
for k,v in Counter(ra).most_common(): print(f"  {k:22s} {v}")
print("=== B: NO_UNITY 표본 50 — 엔진/이미지 마커 ===")
for k,v in Counter(rb).most_common(): print(f"  {k:40s} {v}")
