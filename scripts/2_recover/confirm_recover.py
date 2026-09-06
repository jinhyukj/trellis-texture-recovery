# shard1 확정 회수 전수판: 기록(meta/prefab)만 채택, 슬롯 단위, 트리검증, 재개, 불변식 검사
# usage: python confirm_recover.py [repo_limit]
# env: CR_WORKERS(16) CR_TMULT(1) CR_KEYS(파일: repo key 목록 제한)
import os, re, subprocess, shutil, glob, sys, time, csv
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP="/workspace/jh/cr_tmp"; OUT=f"{B}/unity_confirmed"; DONE=f"{OUT}/.done"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
SLOTRE=re.compile(r"-\s+(\w+):\s*\n\s+m_Texture:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
COLRE=re.compile(r"_Color:\s*\{r:\s*([\d.eE+-]+),\s*g:\s*([\d.eE+-]+),\s*b:\s*([\d.eE+-]+),\s*a:\s*([\d.eE+-]+)")
TM=float(os.environ.get("CR_TMULT","1"))
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")

def run(cmd,timeout,cwd=None,input=None):
    return subprocess.run(cmd,env=ENV,timeout=timeout*TM,cwd=cwd,capture_output=True,text=True,errors="replace",input=input)

def esc(p): return "/"+re.sub(r"([\[\]*?])", r"\\\1", p)

def build_tasks():
    st=pd.read_csv(f"{B}/shards/shard1_texture_status_v2.csv")
    rec=pd.read_csv(f"{B}/shards/shard1_unity_recovery.csv")[["sha256","result"]]
    md=pd.read_csv(f"{B}/metadata.csv"); fid=dict(zip(md.sha256,md.file_identifier))
    BK={"TEX_MISSING","NO_REF_OR_EMBEDDED","TEX_PARTIAL","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"}
    m=st[st.tex_status.isin(BK)].merge(rec,on="sha256",how="left")
    m=m[m.result!="NO_UNITY"]
    tasks={}
    for r in m.itertuples():
        f=str(fid.get(r.sha256,""))
        if "github.com" not in f: continue
        p=f.split("github.com/")[1].split("/")
        if len(p)<5: continue
        key=f"{p[0]}__{p[1]}"
        tasks.setdefault(key,{"org":p[0],"repo":p[1],"items":[]})["items"].append(
            (r.sha256,r.tex_status,r.shard_path,p[3],"/".join(p[4:])))
    return tasks

def process(arg):
    key,t=arg
    rd=os.path.join(TMP,key)
    rows=[]; files=[]; maps=[]
    def flush():
        for suf,data in [(".csv",rows),(".files.csv",files),(".map.csv",maps)]:
            with open(f"{DONE}/{key}{suf}.tmp","w",newline="") as fh: csv.writer(fh).writerows(data)
            os.replace(f"{DONE}/{key}{suf}.tmp",f"{DONE}/{key}{suf}")
        shutil.rmtree(rd,ignore_errors=True)
    try:
        time.sleep(0.2)
        r=run(["git","clone","--filter=blob:none","--no-checkout","--quiet",
            f"https://github.com/{t['org']}/{t['repo']}.git",rd],600)
        if r.returncode!=0:
            rows.extend([[it[0],it[1],it[2],"CLONE_FAIL",0,0,0,""] for it in t["items"]]); flush(); return key
        run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.meta","*.mat","*.prefab","*.unity"],300)
        for commit in sorted(set(it[3] for it in t["items"])):
            co=run(["git","-C",rd,"checkout","--quiet","--force",commit],1800)
            if co.returncode!=0:
                rows.extend([[it[0],it[1],it[2],"CHECKOUT_FAIL",0,0,0,""] for it in t["items"] if it[3]==commit]); continue
            tree=set(run(["git","-C",rd,"-c","core.quotepath=false","ls-tree","-r","--name-only",commit],600).stdout.splitlines())
            g2p={}
            for mp in glob.glob(f"{rd}/**/*.meta",recursive=True):
                m2=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
                if m2: g2p[m2.group(1)]=os.path.relpath(mp,rd)[:-5]
            scenes=[s for s in glob.glob(f"{rd}/**/*.prefab",recursive=True)+glob.glob(f"{rd}/**/*.unity",recursive=True)
                    if os.path.getsize(s)<=20_000_000]
            matcache={}
            def matinfo(rel):
                if rel not in matcache:
                    fp=os.path.join(rd,rel)
                    if not os.path.exists(fp): matcache[rel]=([],1.0)
                    else:
                        txt=open(fp,encoding="utf8",errors="ignore").read()
                        cm=COLRE.search(txt)
                        alpha=float(cm.group(4)) if cm else 1.0
                        matcache[rel]=(SLOTRE.findall(txt),alpha)
                return matcache[rel]
            need=set()
            pend=[]
            for sha,bucket,sp,cm,inner in [it for it in t["items"] if it[3]==commit]:
                mm=os.path.join(rd,inner+".meta")
                if not os.path.exists(mm):
                    rows.append([sha,bucket,sp,"NO_MESH_META",0,0,0,""]); continue
                mg=GUID.search(open(mm,encoding="utf8",errors="ignore").read(4096))
                if not mg:
                    rows.append([sha,bucket,sp,"NO_MESH_META",0,0,0,""]); continue
                meshguid=mg.group(1)
                mats=set(); source=set()
                for g in GUID.findall(open(mm,encoding="utf8",errors="ignore").read()):
                    if g!=meshguid and g2p.get(g,"").endswith(".mat"): mats.add((None,g2p[g])); source.add("META")
                for sf in scenes:
                    txt=open(sf,encoding="utf8",errors="ignore").read()
                    if meshguid not in txt: continue
                    docs=re.split(r"^--- !u!",txt,flags=re.M)
                    go2mesh=set(); go2arr={}
                    for doc in docs:
                        if doc.startswith("137") and meshguid in doc:
                            arr=re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)",doc)
                            if arr:
                                for i,mref in enumerate(re.findall(r"\{[^}]*\}",arr.group(1))):
                                    gm=GUID.search(mref)
                                    if gm and g2p.get(gm.group(1),"").endswith(".mat"):
                                        mats.add((i,g2p[gm.group(1)])); source.add("PREFAB")
                        gm2=re.search(r"m_GameObject:\s*\{fileID:\s*(\d+)",doc)
                        if not gm2: continue
                        go=gm2.group(1)
                        if doc.startswith("33") and meshguid in doc: go2mesh.add(go)
                        if doc.startswith("23"):
                            arr=re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)",doc)
                            if arr: go2arr[go]=arr.group(1)
                    for go in go2mesh:
                        if go in go2arr:
                            for i,mref in enumerate(re.findall(r"\{[^}]*\}",go2arr[go])):
                                gm=GUID.search(mref)
                                if gm and g2p.get(gm.group(1),"").endswith(".mat"):
                                    mats.add((i,g2p[gm.group(1)])); source.add("PREFAB")
                if not mats:
                    rows.append([sha,bucket,sp,"NO_RECORD",0,0,0,""]); continue
                src="+".join(sorted(source))
                texrows=[]; absent=0
                for slot_i,matrel in sorted(mats,key=str):
                    slots,alpha=matinfo(matrel)
                    for ts,g in slots:
                        tp=g2p.get(g,"")
                        if not tp.lower().endswith(IMG): continue
                        if tp in tree:
                            texrows.append((slot_i,matrel,ts,tp,alpha)); need.add(tp)
                        else: absent+=1
                if not texrows:
                    lab=f"{src}_TEX_ABSENT" if absent else f"{src}_COLORS_ONLY"
                    rows.append([sha,bucket,sp,lab,len(mats),0,0,""]); continue
                pend.append((sha,bucket,sp,src,len(mats),texrows,absent))
            if need:
                pats=["*.meta","*.mat","*.prefab","*.unity"]+[esc(p) for p in sorted(need)]
                run(["git","-C",rd,"sparse-checkout","set","--no-cone","--stdin"],900,input="\n".join(pats))
                run(["git","-C",rd,"checkout","--quiet","--force",commit],1800)
                copied={}
                for p2 in sorted(need):
                    sp2=os.path.join(rd,p2)
                    if not os.path.exists(sp2): continue
                    dst=os.path.join(OUT,key,p2)
                    if not os.path.exists(dst):
                        os.makedirs(os.path.dirname(dst),exist_ok=True)
                        shutil.copy2(sp2,dst+".tmp"); os.replace(dst+".tmp",dst)
                        files.append([key,p2,os.path.getsize(dst)])
                    copied[p2]=True
                for sha,bucket,sp,src,nm,texrows,absent in pend:
                    got=0
                    for slot_i,matrel,ts,tp,alpha in texrows:
                        ok=1 if copied.get(tp) else 0; got+=ok
                        maps.append([sha,sp,key,("" if slot_i is None else slot_i),matrel,ts,tp,alpha,ok])
                    lab=f"{src}_CONFIRMED" if got>0 else f"{src}_TEX_ABSENT"
                    rows.append([sha,bucket,sp,lab,nm,len(texrows),got,("ALPHA0" if any(a==0 for *_,a in texrows) else "")])
        flush()
    except Exception as e:
        rows=[[it[0],it[1],it[2],f"ERR:{type(e).__name__}",0,0,0,""] for it in t["items"]]
        flush()
    return key

if __name__=="__main__":
    limit=int(sys.argv[1]) if len(sys.argv)>1 else 0
    os.makedirs(TMP,exist_ok=True); os.makedirs(DONE,exist_ok=True)
    tasks=build_tasks()
    keys=sorted(tasks)
    kf=os.environ.get("CR_KEYS","")
    if kf:
        want=set(open(kf).read().split()); keys=[k for k in keys if k in want]
    if limit: keys=keys[:limit]
    todo=[(k,tasks[k]) for k in keys if not os.path.exists(f"{DONE}/{k}.csv")]
    print(f"대상 repo {len(keys)} 중 신규 {len(todo)} / mesh {sum(len(tasks[k]['items']) for k in keys)}",flush=True)
    W=int(os.environ.get("CR_WORKERS","16"))
    t0=time.time(); n=0
    with Pool(W) as p:
        for _ in p.imap_unordered(process,todo,chunksize=1):
            n+=1
            if n%100==0:
                el=time.time()-t0
                print(f"{n}/{len(todo)} ({n/el*60:.0f} repo/min, ETA {(len(todo)-n)*el/n/3600:.1f}h)",flush=True)
    # ── 머지 ──
    def merge(suf,hdr,name):
        acc=[]
        for f in glob.glob(f"{DONE}/*{suf}"):
            base=f[:-len(suf)]
            if suf==".csv" and (f.endswith(".files.csv") or f.endswith(".map.csv")): continue
            acc+=list(csv.reader(open(f)))
        with open(f"{B}/shards/{name}","w",newline="") as fh:
            w=csv.writer(fh); w.writerow(hdr); w.writerows(acc)
        return len(acc)
    n1=merge(".csv",["sha256","bucket","shard_path","result","n_mats","n_slot_tex","n_tex_dl","flags"],"shard1_confirmed_results.csv")
    n2=merge(".files.csv",["repo","path","bytes"],"shard1_confirmed_files.csv")
    n3=merge(".map.csv",["sha256","shard_path","repo","slot_index","mat_path","tex_slot","texture_path","mat_alpha","downloaded"],"shard1_confirmed_map.csv")
    print(f"결과 {n1}행 / 파일 {n2} / 맵 {n3}")
    # ── 불변식 검사 ──
    df=pd.read_csv(f"{B}/shards/shard1_confirmed_results.csv")
    bad1=df[(df.result.str.endswith("_CONFIRMED"))&(df.n_tex_dl<=0)]
    bad2=df[(df.result.str.endswith("_TEX_ABSENT"))&(df.n_tex_dl>0)]
    import random
    mp=pd.read_csv(f"{B}/shards/shard1_confirmed_map.csv")
    ok=mp[mp.downloaded==1]
    samp=ok.sample(min(200,len(ok)),random_state=1) if len(ok) else ok
    miss=sum(0 if os.path.exists(os.path.join(OUT,r.repo,r.texture_path)) else 1 for r in samp.itertuples())
    print("\n== 불변식 검사 ==")
    print(f"CONFIRMED인데 n_tex_dl=0: {len(bad1)}  |  TEX_ABSENT인데 다운로드>0: {len(bad2)}  |  맵 표본 200 중 실물 없음: {miss}")
    print("PASS" if (len(bad1)==0 and len(bad2)==0 and miss==0) else "FAIL — 보고 전 원인 확인 필요")
    print("\n== 결과 분포 ==")
    print(df.result.value_counts().to_string())
    print(f"\n확정+텍스처: {(df.result.str.endswith('_CONFIRMED')).sum()} / {len(df)}")
