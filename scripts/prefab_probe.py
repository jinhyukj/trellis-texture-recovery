# prefab/씬 3단 추적 정찰 v2: blob 크기 조회 제거(ls-tree -l 금지), 병렬 6
import os, re, subprocess, shutil, glob, sys
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP="/workspace/jh/pfprobe_tmp"
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
d=pd.read_csv(f"{B}/shards/shard1_unity_texture_binding.csv")
md=pd.read_csv(f"{B}/metadata.csv"); fid=dict(zip(md.sha256,md.file_identifier))
tgt=d[d.binding.isin(["MEDIUM_AMBIG","MEDIUM_NAME","MEDIUM_SINGLE","MEDIUM_UNIQUE_TEX"])].drop_duplicates("sha256").sample(30,random_state=13)

def probe_one(arg):
    sha,binding,mat_path=arg
    f=str(fid.get(sha,""))
    p=f.split("github.com/")[1].split("/")
    org,repo,commit,inner=p[0],p[1],p[3],"/".join(p[4:])
    rd=os.path.join(TMP,f"{org}__{repo}__{sha[:8]}")
    try:
        subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],env=ENV,timeout=600,check=True,capture_output=True)
        subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.meta","*.prefab","*.unity"],env=ENV,timeout=300,capture_output=True)
        subprocess.run(["git","-C",rd,"checkout","--quiet","--force",commit],env=ENV,timeout=1800,capture_output=True)
        g2p={}
        for mp in glob.glob(f"{rd}/**/*.meta",recursive=True):
            m=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
            if m: g2p[m.group(1)]=os.path.relpath(mp,rd)[:-5]
        meshguid=None
        mm=os.path.join(rd,inner+".meta")
        if os.path.exists(mm):
            m=GUID.search(open(mm,encoding="utf8",errors="ignore").read(4096))
            if m: meshguid=m.group(1)
        if not meshguid:
            shutil.rmtree(rd,ignore_errors=True); return (binding,"NO_MESH_META")
        found=set()
        scenes=glob.glob(f"{rd}/**/*.prefab",recursive=True)+glob.glob(f"{rd}/**/*.unity",recursive=True)
        for sf in scenes:
            if os.path.getsize(sf)>20_000_000: continue
            txt=open(sf,encoding="utf8",errors="ignore").read()
            if meshguid not in txt: continue
            docs=re.split(r"^--- !u!", txt, flags=re.M)
            go2mesh=set(); go2mats={}
            for doc in docs:
                gm=re.search(r"m_GameObject:\s*\{fileID:\s*(\d+)", doc)
                if doc.startswith("137") and meshguid in doc:
                    for g in GUID.findall(doc):
                        if g2p.get(g,"").endswith(".mat"): found.add(g2p[g])
                if not gm: continue
                go=gm.group(1)
                if doc.startswith("33") and meshguid in doc: go2mesh.add(go)
                if doc.startswith("23"):
                    mats=[g for g in GUID.findall(doc) if g2p.get(g,"").endswith(".mat")]
                    if mats: go2mats.setdefault(go,[]).extend(mats)
            for go in go2mesh:
                for g in go2mats.get(go,[]): found.add(g2p[g])
        shutil.rmtree(rd,ignore_errors=True)
        if found:
            return (binding,"PREFAB_OK_AGREE" if mat_path in found else "PREFAB_OK_DIFFERENT")
        return (binding,"NO_SCENE_USE")
    except Exception as e:
        shutil.rmtree(rd,ignore_errors=True)
        return (binding,f"ERR:{type(e).__name__}")

if __name__=="__main__":
    os.makedirs(TMP,exist_ok=True)
    res=[]
    with Pool(6) as p:
        for x in p.imap_unordered(probe_one, [(x.sha256,x.binding,x.mat_path) for x in tgt.itertuples()]):
            res.append(x); sys.stdout.write("."); sys.stdout.flush()
    print()
    from collections import Counter
    print("전체:", dict(Counter(x[1] for x in res)))
    for b in ["MEDIUM_SINGLE","MEDIUM_NAME","MEDIUM_UNIQUE_TEX","MEDIUM_AMBIG"]:
        s=[x[1] for x in res if x[0]==b]
        if s: print(f"  {b:18s}", dict(Counter(s)))
