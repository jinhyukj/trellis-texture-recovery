# 정제 바인딩: mesh → (재질, 슬롯, 텍스처) 확정 연결표 생성
# 로컬 .mat 파싱 + 원천에서 텍스처 .meta만 추가 fetch → GUID 해석
import os, re, sys, csv, glob, shutil, subprocess, time, difflib
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
UR=f"{B}/unity_recovered"; DONE=f"{UR}/.bind_done"; TMP="/workspace/jh/bind_tmp"
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
SLOT=re.compile(r"-\s+(\w+):\s*\n\s+m_Texture:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
KIND={"_MainTex":"albedo","_BaseMap":"albedo","_BaseColorMap":"albedo","_BumpMap":"normal","_NormalMap":"normal","_MetallicGlossMap":"metallic","_SpecGlossMap":"specular","_OcclusionMap":"ao","_EmissionMap":"emission","_ParallaxMap":"height","_DetailAlbedoMap":"detail_albedo","_DetailNormalMap":"detail_normal"}
TM=float(os.environ.get("UB_TMULT","2"))
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
def run(cmd,timeout,cwd=None,input=None):
    return subprocess.run(cmd,env=ENV,timeout=timeout*TM,cwd=cwd,capture_output=True,text=True,errors="replace",input=input)
def build_tasks():
    m=pd.read_csv(f"{B}/shards/shard1_unity_recovery_map.csv")
    md=pd.read_csv(f"{B}/metadata.csv"); fid=dict(zip(md.sha256,md.file_identifier))
    tasks={}
    for key,grp in m.groupby("repo"):
        items=[]
        for sha,g2 in grp.groupby("sha256"):
            f=str(fid.get(sha,""))
            if "github.com" not in f: continue
            p=f.split("github.com/")[1].split("/")
            items.append((sha, g2.iloc[0].shard_path, p[3], "/".join(p[4:]), sorted(set(g2.texture_path))))
        if items:
            org,repo=key.split("__",1)
            tasks[key]={"org":org,"repo":repo,"items":items}
    return tasks
def esc(p): return "/"+re.sub(r"([\[\]*?])", r"\\\1", p)
def process(arg):
    key,t=arg
    rd=os.path.join(TMP,key); rows=[]
    out=f"{DONE}/{key}.csv"
    lr=os.path.join(UR,key)
    def flush():
        with open(out+".tmp","w",newline="") as fh: csv.writer(fh).writerows(rows)
        os.replace(out+".tmp",out); shutil.rmtree(rd,ignore_errors=True)
    try:
        time.sleep(0.3)
        # 로컬 guid→경로 (mat/mesh meta는 이미 로컬에 있음)
        lg2p={}
        for mp in glob.glob(f"{lr}/**/*.meta",recursive=True):
            mm=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
            if mm: lg2p[mm.group(1)]=os.path.relpath(mp,lr)[:-5]
        # 원천에서 텍스처 .meta fetch
        alltex=sorted(set(tx for it in t["items"] for tx in it[4]))
        need=[tx+".meta" for tx in alltex]
        org=t["org"]; repo=t["repo"]
        r=run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],300)
        if r.returncode!=0:
            for it in t["items"]: rows.append([it[0],it[1],"","","","CLONE_FAIL"])
            flush(); return key
        bycommit={}
        for it in t["items"]: bycommit.setdefault(it[2],[]).append(it)
        for commit,items in bycommit.items():
            sp=run(["git","sparse-checkout","set","--no-cone","--stdin"],900,cwd=rd,input="\n".join(esc(p) for p in need))
            co=run(["git","checkout","--quiet","--force",commit],900,cwd=rd)
            g2tex={}
            for tx in alltex:
                mp=os.path.join(rd,tx+".meta")
                if os.path.exists(mp):
                    mm=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
                    if mm: g2tex[mm.group(1)]=tx
            # 로컬 .mat 파싱: matrel → [(slot,guid)]
            matslots={}
            for mp in glob.glob(f"{lr}/**/*.mat",recursive=True):
                rel=os.path.relpath(mp,lr)
                txt=open(mp,encoding="utf8",errors="ignore").read()
                matslots[rel]=SLOT.findall(txt)
            for sha,sp2,cm,inner,texs in items:
                texset=set(texs)
                mats=[]; conf=""
                mm=os.path.join(lr,inner+".meta")
                if os.path.exists(mm):
                    own=[lg2p.get(g,"") for g in GUID.findall(open(mm,encoding="utf8",errors="ignore").read())]
                    mats=[p for p in own if p.endswith(".mat") and p in matslots]
                    if mats: conf="HIGH"
                if not mats:
                    mdir=os.path.dirname(inner)
                    cand=[p for p in matslots if os.path.dirname(p)==mdir or (mdir and p.startswith(mdir+"/"))]
                    if not cand:
                        pdir=os.path.dirname(mdir)
                        cand=[p for p in matslots if os.path.dirname(p)==pdir or (pdir and p.startswith(pdir+"/"))]
                    if not cand: cand=list(matslots)
                    if len(cand)==1: mats,conf=cand,"MEDIUM_SINGLE"
                    elif cand:
                        stem=os.path.splitext(os.path.basename(inner))[0].lower()
                        scored=sorted(cand,key=lambda p:-difflib.SequenceMatcher(None,stem,os.path.splitext(os.path.basename(p))[0].lower()).ratio())
                        best=scored[0]
                        ratio=difflib.SequenceMatcher(None,stem,os.path.splitext(os.path.basename(best))[0].lower()).ratio()
                        if ratio>=0.55: mats,conf=[best],"MEDIUM_NAME"
                        else: mats,conf=scored[:3],"MEDIUM_AMBIG"
                emitted=False
                for mp in mats:
                    for slot,g in matslots.get(mp,[]):
                        tx=g2tex.get(g,"")
                        if not tx or tx not in texset: continue
                        rows.append([sha,sp2,mp,slot,KIND.get(slot,"other"),tx,conf]); emitted=True
                if not emitted:
                    rows.append([sha,sp2,mats[0] if mats else "","","","",conf if conf else "NO_BINDING"])
        flush()
    except Exception as e:
        rows=[[it[0],it[1],"","","","",f"ERR:{type(e).__name__}"] for it in t["items"]]
        flush()
    return key
if __name__=="__main__":
    limit=int(sys.argv[1]) if len(sys.argv)>1 else 0
    os.makedirs(DONE,exist_ok=True); os.makedirs(TMP,exist_ok=True)
    tasks=build_tasks()
    keys=sorted(tasks)
    kf=os.environ.get("UB_KEYS","")
    if kf: 
        want=set(open(kf).read().split()); keys=[k for k in keys if k in want]
    if limit: keys=keys[:limit]
    todo=[(k,tasks[k]) for k in keys if not os.path.exists(f"{DONE}/{k}.csv")]
    print(f"대상 repo {len(keys)} 중 신규 {len(todo)}",flush=True)
    W=int(os.environ.get("UB_WORKERS","8"))
    t0=time.time(); n=0
    with Pool(W) as p:
        for _ in p.imap_unordered(process,todo,chunksize=1):
            n+=1
            if n%50==0:
                el=time.time()-t0
                print(f"{n}/{len(todo)} ({n/el*60:.0f} repo/min, ETA {(len(todo)-n)*el/n/3600:.1f}h)",flush=True)
    allrows=[]
    for f in glob.glob(f"{DONE}/*.csv"): allrows+=list(csv.reader(open(f)))
    outp=f"{B}/shards/shard1_unity_texture_binding.csv"
    with open(outp,"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["sha256","shard_path","mat_path","slot","slot_kind","texture_path","binding"]); w.writerows(allrows)
    d=pd.read_csv(outp)
    print("\n총",len(d),"행 / mesh",d.sha256.nunique())
    print(d.binding.value_counts().to_string())
