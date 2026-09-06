# 신규 1단계 파이프라인 smoke test: 층화 100 mesh (Unity-only), 기록(meta/prefab)만 채택, 슬롯 단위
import os, re, subprocess, shutil, glob, sys, time, csv
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP="/workspace/jh/smoke100_tmp"; OUT="/workspace/jh/smoke100"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
GUID=re.compile(r"guid:\s*([0-9a-f]{32})")
SLOTRE=re.compile(r"-\s+(\w+):\s*\n\s+m_Texture:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
ENV=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")

def esc(p): return "/"+re.sub(r"([\[\]*?])", r"\\\1", p)

def build_sample():
    st=pd.read_csv(f"{B}/shards/shard1_texture_status_v2.csv")
    rec=pd.read_csv(f"{B}/shards/shard1_unity_recovery.csv")[["sha256","result"]]
    md=pd.read_csv(f"{B}/metadata.csv")
    fid=dict(zip(md.sha256,md.file_identifier))
    m=st.merge(rec,on="sha256",how="left")
    m=m[m.result!="NO_UNITY"]  # Unity 아님 사전 제외 (판정 없는 PARTIAL 일부는 유지)
    buckets=["TEX_MISSING","NO_REF_OR_EMBEDDED","TEX_PARTIAL","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"]
    sel=[]
    for b in buckets:
        s=m[m.tex_status==b]
        s=s[s.sha256.map(lambda x:"github.com" in str(fid.get(x,"")))]
        sel.append(s.sample(min(20,len(s)),random_state=77))
    sel=pd.concat(sel)
    tasks={}
    for r in sel.itertuples():
        f=str(fid[r.sha256]); p=f.split("github.com/")[1].split("/")
        key=f"{p[0]}__{p[1]}"
        tasks.setdefault(key,{"org":p[0],"repo":p[1],"items":[]})["items"].append(
            (r.sha256,r.tex_status,r.shard_path,p[3],"/".join(p[4:])))
    return tasks

def process(arg):
    key,t=arg
    rd=os.path.join(TMP,key); rows=[]; t0=time.time()
    try:
        subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",
            f"https://github.com/{t['org']}/{t['repo']}.git",rd],env=ENV,timeout=600,check=True,capture_output=True)
        subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","*.meta","*.mat","*.prefab","*.unity"],env=ENV,timeout=300,capture_output=True)
        for commit in set(it[3] for it in t["items"]):
            subprocess.run(["git","-C",rd,"checkout","--quiet","--force",commit],env=ENV,timeout=1800,capture_output=True)
            g2p={}
            for mp in glob.glob(f"{rd}/**/*.meta",recursive=True):
                m=GUID.search(open(mp,encoding="utf8",errors="ignore").read(4096))
                if m: g2p[m.group(1)]=os.path.relpath(mp,rd)[:-5]
            scenes=[s for s in glob.glob(f"{rd}/**/*.prefab",recursive=True)+glob.glob(f"{rd}/**/*.unity",recursive=True)
                    if os.path.getsize(s)<=20_000_000]
            for sha,bucket,sp,cm,inner in t["items"]:
                if cm!=commit: continue
                mm=os.path.join(rd,inner+".meta")
                if not os.path.exists(mm):
                    rows.append([sha,bucket,sp,"NO_MESH_META",0,0,time.time()-t0]); continue
                mg=GUID.search(open(mm,encoding="utf8",errors="ignore").read(4096))
                if not mg:
                    rows.append([sha,bucket,sp,"NO_MESH_META",0,0,time.time()-t0]); continue
                meshguid=mg.group(1)
                # (a) mesh.meta externalObjects
                mats=set(); source=""
                metatxt=open(mm,encoding="utf8",errors="ignore").read()
                for g in GUID.findall(metatxt):
                    if g!=meshguid and g2p.get(g,"").endswith(".mat"): mats.add((None,g2p[g]))
                if mats: source="META"
                # (b) prefab/scene 슬롯 추적
                slotmats=[]
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
                                        slotmats.append((i,g2p[gm.group(1)]))
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
                                    slotmats.append((i,g2p[gm.group(1)]))
                if slotmats:
                    source="PREFAB" if not source else "META+PREFAB"
                    for i,mp2 in slotmats: mats.add((i,mp2))
                if not mats:
                    rows.append([sha,bucket,sp,"NO_RECORD",0,0,time.time()-t0]); continue
                # 재질 → 슬롯별 텍스처
                texneed={}
                for slot_i,matrel in mats:
                    fp=os.path.join(rd,matrel)
                    if not os.path.exists(fp): continue
                    for ts,g in SLOTRE.findall(open(fp,encoding="utf8",errors="ignore").read()):
                        tp=g2p.get(g,"")
                        if tp.lower().endswith(IMG): texneed[(slot_i,matrel,ts)]=tp
                if not texneed:
                    rows.append([sha,bucket,sp,f"{source}_COLORS_ONLY",len(mats),0,time.time()-t0]); continue
                pats=["*.meta","*.mat","*.prefab","*.unity"]+[esc(p) for p in sorted(set(texneed.values()))]
                subprocess.run(["git","-C",rd,"sparse-checkout","set","--no-cone","--stdin"],input="\n".join(pats),env=ENV,timeout=900,capture_output=True,text=True)
                subprocess.run(["git","-C",rd,"checkout","--quiet","--force",commit],env=ENV,timeout=1800,capture_output=True)
                case=os.path.join(OUT,"cases",sha[:12]); os.makedirs(case,exist_ok=True)
                got=0
                with open(os.path.join(case,"binding.tsv"),"w") as fh:
                    fh.write(f"# {sp}\n")
                    for (slot_i,matrel,ts),tp in sorted(texneed.items(),key=str):
                        src=os.path.join(rd,tp)
                        if os.path.exists(src):
                            shutil.copy2(src,os.path.join(case,os.path.basename(tp))); got+=1
                            fh.write(f"{slot_i}\t{matrel}\t{ts}\t{os.path.basename(tp)}\n")
                rows.append([sha,bucket,sp,f"{source}_CONFIRMED",len(mats),got,time.time()-t0])
    except Exception as e:
        for it in t["items"]:
            rows.append([it[0],it[1],it[2],f"ERR:{type(e).__name__}",0,0,time.time()-t0])
    shutil.rmtree(rd,ignore_errors=True)
    return rows

if __name__=="__main__":
    os.makedirs(TMP,exist_ok=True); os.makedirs(f"{OUT}/cases",exist_ok=True)
    tasks=build_tasks=build_sample()
    todo=sorted(tasks.items())
    print(f"표본 mesh {sum(len(t['items']) for _,t in todo)} / repo {len(todo)}",flush=True)
    allrows=[]
    with Pool(8) as p:
        for rows in p.imap_unordered(process,todo):
            allrows+=rows; sys.stdout.write("."); sys.stdout.flush()
    print()
    with open(f"{OUT}/results.csv","w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["sha256","bucket","shard_path","result","n_mats","n_tex","repo_sec"]); w.writerows(allrows)
    df=pd.DataFrame(allrows,columns=["sha","bucket","sp","result","nm","nt","sec"])
    print("\n== 버킷별 결과 ==")
    print(df.groupby(["bucket","result"]).size().to_string())
    conf=df[df.result.str.endswith("_CONFIRMED")]
    print(f"\n확정+텍스처 획득: {len(conf)}/{len(df)}")
    print("repo당 소요(초): 중앙값 {:.0f} / 90퍼센타일 {:.0f} / 최대 {:.0f}".format(df.sec.median(),df.sec.quantile(.9),df.sec.max()))
