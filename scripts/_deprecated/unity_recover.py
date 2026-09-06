# shard1 텍스처-없음 4버킷 전체 대상 Unity .mat/.meta 체인 텍스처 회수
# usage: python unity_recover.py [repo_limit]   (0=전체)  env: UR_WORKERS(기본16) UR_DELAY(기본0.2)
import os, re, sys, csv, glob, shutil, subprocess, time
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OUT=f"{B}/unity_recovered"; DONE=f"{OUT}/.done"; TMP="/workspace/jh/ur_tmp"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
BK={"TEX_MISSING","NO_REF_OR_EMBEDDED","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"}
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
MAXTEX=300; MAXBYTES=1_000_000_000
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
DELAY=float(os.environ.get("UR_DELAY","0.2"))
def build_tasks():
    df=pd.read_csv(f"{B}/shards/shard1_texture_status.csv")
    md=pd.read_csv(f"{B}/metadata.csv")
    fid=dict(zip(md.sha256, md.file_identifier))
    t=df[df.tex_status.isin(BK)]
    tasks={}
    for r in t.itertuples(index=False):
        f=str(fid.get(r.sha256,""))
        if "github.com" not in f: continue
        parts=f.split("github.com/")[1].split("/")
        if len(parts)<5: continue
        org,repo,commit=parts[0],parts[1],parts[3]; inner="/".join(parts[4:])
        key=f"{org}__{repo}"
        tasks.setdefault(key,{"org":org,"repo":repo,"items":[]})["items"].append((r.sha256,r.shard_path,r.tex_status,commit,inner))
    return tasks
TM=float(os.environ.get("UR_TMULT","1"))
def run(cmd,timeout,cwd=None,input=None):
    return subprocess.run(cmd,env=ENV,timeout=timeout*TM,cwd=cwd,capture_output=True,text=True,errors="replace",input=input)
def process(arg):
    key,t=arg
    org,repo=t["org"],t["repo"]; rd=os.path.join(TMP,key)
    rows=[]; done_csv=f"{DONE}/{key}.csv"; files=[]; mapping=[]
    def flush(status_all=None):
        if status_all is not None:
            for it in t["items"]: rows.append([it[0],it[1],it[2],status_all,0,0,0,""])
        with open(done_csv+".tmp","w",newline="") as fh:
            csv.writer(fh).writerows(rows)
        with open(done_csv[:-4]+".files.csv.tmp","w",newline="") as fh:
            csv.writer(fh).writerows(files)
        os.replace(done_csv[:-4]+".files.csv.tmp",done_csv[:-4]+".files.csv")
        with open(done_csv[:-4]+".map.csv.tmp","w",newline="") as fh:
            csv.writer(fh).writerows(mapping)
        os.replace(done_csv[:-4]+".map.csv.tmp",done_csv[:-4]+".map.csv")
        os.replace(done_csv+".tmp",done_csv)
        shutil.rmtree(rd,ignore_errors=True)
    try:
        time.sleep(DELAY)
        r=run(["git","clone","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",rd],300)
        if r.returncode!=0: flush("CLONE_FAIL"); return key
        bycommit={}
        for it in t["items"]: bycommit.setdefault(it[3],[]).append(it)
        dl_total=0; dl_bytes=0
        for commit,items in bycommit.items():
            pending=[]
            ls=run(["git","-c","core.quotepath=false","ls-tree","-r","--name-only",commit],180,cwd=rd)
            tree=set(ls.stdout.splitlines())
            if not any(p.endswith(".meta") for p in tree):
                for it in items: rows.append([it[0],it[1],it[2],"NO_UNITY",0,0,0,""])
                continue
            run(["git","sparse-checkout","set","--no-cone","*.mat","*.meta"],120,cwd=rd)
            co=run(["git","checkout","--quiet","--force",commit],900,cwd=rd)
            if co.returncode!=0:
                for it in items: rows.append([it[0],it[1],it[2],"CHECKOUT_FAIL",0,0,0,""])
                continue
            g2p={}
            for mp in glob.glob(f"{rd}/**/*.meta",recursive=True):
                try: head=open(mp,encoding="utf8",errors="ignore").read(4096)
                except: continue
                m=GUID.search(head)
                if m: g2p[m.group(1)]=os.path.relpath(mp,rd)[:-5]
            def mat_textures(matrel):
                try: txt=open(os.path.join(rd,matrel),encoding="utf8",errors="ignore").read()
                except: return []
                out=[]
                for g in GUID.findall(txt):
                    p=g2p.get(g,"")
                    if p.lower().endswith(IMG) and p in tree: out.append(p)
                return out
            need=set()
            for it in items:
                sha,sp,bucket,_,inner=it
                mats=[]; conf="NONE"
                mm=os.path.join(rd,inner+".meta")
                if os.path.exists(mm):
                    txt=open(mm,encoding="utf8",errors="ignore").read()
                    own=[g2p.get(g,"") for g in GUID.findall(txt)]
                    mats=[p for p in own if p.endswith(".mat")]
                    if mats: conf="HIGH"
                if not mats:
                    mdir=os.path.dirname(inner); pdir=os.path.dirname(mdir)
                    allmats=[os.path.relpath(p,rd) for p in glob.glob(f"{rd}/**/*.mat",recursive=True)]
                    mats=[p for p in allmats if (mdir and (os.path.dirname(p)==mdir or p.startswith(mdir+"/")))]
                    if not mats and pdir:
                        mats=[p for p in allmats if os.path.dirname(p)==pdir or p.startswith(pdir+"/")]
                    if mats: conf="MEDIUM"
                texs=set()
                for mp in mats: texs.update(mat_textures(mp))
                texs=sorted(texs)[:MAXTEX]
                if texs:
                    for p in texs: need.add(p)
                    for mp in mats: need.add(mp); need.add(mp+".meta")
                    need.add(inner+".meta")
                rows.append([sha,sp,bucket,conf if texs else ("CHAIN_EMPTY" if conf!="NONE" else "NO_MAT"),len(mats),len(texs),0,";".join(texs[:6])])
                pending.append((len(rows)-1,texs))
            need={p for p in need if p in tree}
            if need:
                pats=["*.mat","*.meta"]+["/"+re.sub(r"([\[\]*?])", r"\\\1", p) for p in sorted(need)]
                sp_proc=run(["git","sparse-checkout","set","--no-cone","--stdin"],900,cwd=rd,input="\n".join(pats))
                run(["git","checkout","--quiet","--force",commit],900,cwd=rd)
                copied=set()
                for p in sorted(need):
                    srcp=os.path.join(rd,p)
                    if not os.path.exists(srcp): continue
                    sz=os.path.getsize(srcp)
                    if p.lower().endswith(IMG):
                        if dl_bytes+sz>MAXBYTES: continue
                        dl_bytes+=sz; dl_total+=1
                    dst=os.path.join(OUT,key,p)
                    os.makedirs(os.path.dirname(dst),exist_ok=True)
                    shutil.copy2(srcp,dst+".tmp"); os.replace(dst+".tmp",dst)
                    copied.add(p); files.append([key,p,sz])
                for idx,texs in pending:
                    hit=[p for p in texs if p in copied]
                    rows[idx][6]=len(hit)
                    for p in hit: mapping.append([rows[idx][0],rows[idx][1],key,p])
            pending=[]
        flush()
    except Exception as e:
        rows=[[it[0],it[1],it[2],f"ERR:{type(e).__name__}",0,0,0,""] for it in t["items"]]
        flush()
    return key
if __name__=="__main__":
    limit=int(sys.argv[1]) if len(sys.argv)>1 else 0
    os.makedirs(DONE,exist_ok=True); os.makedirs(TMP,exist_ok=True)
    tasks=build_tasks()
    keys=sorted(tasks)
    kf=os.environ.get("UR_KEYS","")
    if kf:
        want=set(open(kf).read().split())
        keys=[k for k in keys if k in want]
    if limit: keys=keys[:limit]
    todo=[(k,tasks[k]) for k in keys if not os.path.exists(f"{DONE}/{k}.csv")]
    print(f"대상 repo {len(keys)} 중 신규 {len(todo)}",flush=True)
    W=int(os.environ.get("UR_WORKERS","16"))
    t0=time.time(); n=0
    with Pool(W) as p:
        for _ in p.imap_unordered(process,todo,chunksize=1):
            n+=1
            if n%50==0:
                el=time.time()-t0
                print(f"{n}/{len(todo)} ({n/el*60:.0f} repo/min, ETA {(len(todo)-n)*el/n/3600:.1f}h)",flush=True)
    # 머지 + 요약
    allrows=[]
    for f in glob.glob(f"{DONE}/*.csv"):
        if f.endswith(".files.csv") or f.endswith(".map.csv"): continue
        with open(f) as fh: allrows += list(csv.reader(fh))
    out=f"{B}/shards/shard1_unity_recovery.csv"
    with open(out,"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["sha256","shard_path","bucket","result","n_mats","n_tex_found","n_tex_downloaded","tex_sample"]); w.writerows(allrows)
    for suffix,hdr,name in [(".files.csv",["repo","path","bytes"],"shard1_unity_recovered_files.csv"),(".map.csv",["sha256","shard_path","repo","texture_path"],"shard1_unity_recovery_map.csv")]:
        acc=[]
        for f in glob.glob(f"{DONE}/*"+suffix):
            with open(f) as fh: acc += list(csv.reader(fh))
        with open(f"{B}/shards/"+name,"w",newline="") as fh:
            w=csv.writer(fh); w.writerow(hdr); w.writerows(acc)
        print(f"{name}: {len(acc)} rows")
    r=pd.read_csv(out)
    print("\n=== 결과 요약 ===")
    print(r.groupby(["bucket","result"]).size().to_string())
    got=r[r.n_tex_downloaded.astype(int)>0]
    print(f"\n텍스처 획득 mesh: {len(got)} / {len(r)} ({len(got)/len(r)*100:.1f}%)")
    print(got.groupby("bucket").size().to_string())
