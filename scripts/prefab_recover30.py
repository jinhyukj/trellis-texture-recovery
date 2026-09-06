# 30 표본 prefab 확정 회수: 기록 있는 mesh의 재질 슬롯별 텍스처를 확보해 케이스 폴더로 저장
import os, re, subprocess, shutil, glob, sys, csv
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP="/workspace/jh/pf30_tmp"; OUT="/workspace/jh/prefab_sample30"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
SLOT=re.compile(r"-\s+(\w+):\s*\n\s+m_Texture:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
d=pd.read_csv(f"{B}/shards/shard1_unity_texture_binding.csv")
md=pd.read_csv(f"{B}/metadata.csv"); fid=dict(zip(md.sha256,md.file_identifier))
tgt=d[d.binding.isin(["MEDIUM_AMBIG","MEDIUM_NAME","MEDIUM_SINGLE","MEDIUM_UNIQUE_TEX"])].drop_duplicates("sha256").sample(30,random_state=13)

def esc(p): return "/"+re.sub(r"([\[\]*?])", r"\\\1", p)

def recover_one(arg):
    sha,binding,shard_path=arg
    f=str(fid.get(sha,""))
    p=f.split("github.com/")[1].split("/")
    org,repo,commit,inner=p[0],p[1],p[3],"/".join(p[4:])
    rd=os.path.join(TMP,f"{org}__{repo}__{sha[:8]}")
    try:
        subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],env=ENV,timeout=600,check=True,capture_output=True)
        subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.meta","*.prefab","*.unity","*.mat"],env=ENV,timeout=300,capture_output=True)
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
            shutil.rmtree(rd,ignore_errors=True); return (sha,binding,shard_path,"NO_MESH_META",[])
        found=set()
        for sf in glob.glob(f"{rd}/**/*.prefab",recursive=True)+glob.glob(f"{rd}/**/*.unity",recursive=True):
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
        if not found:
            shutil.rmtree(rd,ignore_errors=True); return (sha,binding,shard_path,"NO_SCENE_USE",[])
        # 확정 재질들의 슬롯별 텍스처 guid → 경로
        texneed={}
        for matrel in found:
            mp=os.path.join(rd,matrel)
            if not os.path.exists(mp): continue
            for slot,g in SLOT.findall(open(mp,encoding="utf8",errors="ignore").read()):
                tp=g2p.get(g,"")
                if tp.lower().endswith(IMG): texneed[(matrel,slot)]=tp
        if not texneed:
            shutil.rmtree(rd,ignore_errors=True); return (sha,binding,shard_path,"PREFAB_MAT_NO_TEX",sorted(found))
        # 텍스처 blob 추가 checkout
        pats=["*.meta","*.prefab","*.unity","*.mat"]+[esc(p) for p in sorted(set(texneed.values()))]
        subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","--stdin"],input="\n".join(pats),env=ENV,timeout=900,capture_output=True,text=True)
        subprocess.run(["git","-C",rd,"checkout","--quiet","--force",commit],env=ENV,timeout=1800,capture_output=True)
        case=os.path.join(OUT,f"{sha[:12]}")
        os.makedirs(case,exist_ok=True)
        rows=[]
        for (matrel,slot),tp in sorted(texneed.items()):
            src=os.path.join(rd,tp)
            if not os.path.exists(src): continue
            dst=os.path.join(case,os.path.basename(tp))
            shutil.copy2(src,dst)
            rows.append((matrel,slot,os.path.basename(tp)))
        with open(os.path.join(case,"binding.tsv"),"w") as fh:
            fh.write(f"# mesh: {shard_path}\n")
            for a,b2,c in rows: fh.write(f"{a}\t{b2}\t{c}\n")
        shutil.rmtree(rd,ignore_errors=True)
        return (sha,binding,shard_path,"RECOVERED",rows)
    except Exception as e:
        shutil.rmtree(rd,ignore_errors=True)
        return (sha,binding,shard_path,f"ERR:{type(e).__name__}",[])

if __name__=="__main__":
    os.makedirs(TMP,exist_ok=True); os.makedirs(OUT,exist_ok=True)
    args=[(x.sha256,x.binding,x.shard_path) for x in tgt.itertuples()]
    res=[]
    with Pool(6) as p:
        for x in p.imap_unordered(recover_one,args):
            res.append(x); sys.stdout.write("."); sys.stdout.flush()
    print()
    with open(os.path.join(OUT,"cases.tsv"),"w") as fh:
        for sha,b,sp,st,rows in res:
            fh.write(f"{sha}\t{b}\t{st}\t{sp}\t{len(rows)}\n")
    from collections import Counter
    print(dict(Counter(x[3] for x in res)))
    for sha,b,sp,st,rows in res:
        if st=="RECOVERED":
            print(f"  {sha[:12]} [{b}] {sp.split(chr(47))[-1]} → {len(rows)} slot-tex")
