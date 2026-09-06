#!/usr/bin/env python3
"""github partial-clone 다운로더 (B'-strict)
사용: python gh_partial.py <N개> [--workers 32]
blob 없이 트리만 clone → 필요한 파일 blob만 checkout → sha 검증 → 참조 해석·추가 checkout → 추출 트리로 복사.
장부·재개 규약은 기존과 동일 (mesh 존재 = 완료 마커, refs 먼저 복사).
"""
import os, re, sys, json, shutil, hashlib, subprocess, tempfile, time, urllib.parse
from multiprocessing import Pool
import pandas as pd

B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
EX = f"{B}/raw/github/extracted"
MISS = f"{B}/raw/github/missing_fids.txt"
MOD  = f"{B}/raw/github/modified_fids.txt"
TEXRE = re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
if os.path.exists("/workspace/jh/.gh_token"):
    ENV["GIT_ASKPASS"] = "/workspace/jh/.gh_askpass"

def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, env=ENV, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def atomic_copy(src, dst):
    if os.path.exists(dst) or not os.path.exists(src): return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".copytmp"; shutil.copyfile(src, tmp); os.replace(tmp, dst)

def refs_for(path, tree_base):
    """tree_base: {basename_lower: [relpath,…]} — repo 전체 목록(트리)에서 참조 해석"""
    refs = set()
    ext = path.rsplit(".",1)[-1].lower() if "." in path else ""
    def bb(name): return tree_base.get(os.path.basename(name.replace("\\","/")).strip().lower(), [])
    try:
        data = open(path,"rb").read()
        if ext == "obj":
            for mtl in re.findall(r"(?im)^mtllib\s+(.+)$", data.decode("utf8","ignore")):
                refs.update(bb(mtl))
        elif ext == "gltf":
            g = json.loads(data)
            for sec in ("buffers","images"):
                for it in g.get(sec,[]):
                    u = it.get("uri","")
                    if u and not u.startswith("data:"): refs.update(bb(urllib.parse.unquote(u)))
        elif ext == "dae":
            for tex in re.findall(r"<init_from>([^<]+)</init_from>", data.decode("utf8","ignore")):
                refs.update(bb(tex))
        elif ext in ("fbx","blend"):
            for m in TEXRE.findall(data):
                refs.update(bb(m.decode("utf8","ignore")))
    except Exception as e:
        print(f"[refs_for] {os.path.basename(path)}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
    return refs

def mtl_texrefs(path, tree_base):
    refs=set()
    try:
        for tex in re.findall(r"(?im)^map_\w+\s+(.+)$", open(path,"rb").read().decode("utf8","ignore")):
            refs.update(tree_base.get(os.path.basename(tex.strip().split()[-1]).lower(), []))
    except Exception: pass
    return refs

def process_repo(job):
    try:
        return _process_repo(job)
    except Exception as e:
        # 어떤 예외(타임아웃 포함)도 해당 repo만 실패로 — pool 전체를 죽이지 않음
        import time as _t
        return (type(e).__name__.upper()[:20], 0, [], 0.0)

def _process_repo(job):
    (org, repo, commit), items = job   # items: [(inner, sha256, fid), …]
    url = f"https://github.com/{org}/{repo}.git"
    got = missing = modified = 0
    t0=time.time()
    with tempfile.TemporaryDirectory(prefix="ghp_") as td:
        import random as _rnd; time.sleep(_rnd.uniform(0.5, float(os.environ.get("GHP_DELAY","3"))))  # 스로틀
        r = run(["git","clone","--depth","1","--filter=blob:none","--no-checkout","--quiet",url,td], timeout=240)
        if r.returncode != 0:
            err = r.stderr.decode("utf8","ignore")
            if ("could not read Username" in err or "Repository not found" in err
                    or "access denied" in err.lower() or "unavailable due to" in err.lower()):
                # 2차 판정: rate limit도 같은 에러를 내므로 웹 HEAD로 생사 확인 (404/451=진짜 사망)
                try:
                    h = subprocess.run(["curl","-s","-o","/dev/null","-w","%{http_code}",
                                        "-m","15", f"https://github.com/{org}/{repo}"],
                                       stdout=subprocess.PIPE, timeout=20)
                    code = h.stdout.decode().strip()
                except Exception:
                    code = "000"
                if code in ("404","451","410"):
                    return ("REPO_GONE", 0, [f for *_ ,f in items], time.time()-t0)
                return ("CLONE_FAIL", 0, [], time.time()-t0)  # 살아있음 = 제한 — 재시도
            return ("CLONE_FAIL", 0, [], time.time()-t0)
        head = run(["git","rev-parse","HEAD"], cwd=td).stdout.decode().strip()
        if head != commit:
            r = run(["git","fetch","--depth","1","--filter=blob:none","--quiet","origin",commit], cwd=td, timeout=240)
            if r.returncode != 0:
                return ("COMMIT_GONE", 0, [f for *_ ,f in items], time.time()-t0)
        r = run(["git","-c","core.quotepath=false","ls-tree","-r","--name-only",commit], cwd=td, timeout=120)
        if r.returncode != 0:
            return ("LSTREE_FAIL", 0, [], time.time()-t0)
        tree = r.stdout.decode("utf8","ignore").splitlines()
        tset = set(tree)
        tbase = {}
        for t in tree: tbase.setdefault(os.path.basename(t).lower(), []).append(t)
        want = [(i,s,f) for i,s,f in items if i in tset]
        gone = [(i,s,f) for i,s,f in items if i not in tset]
        if want:
            run(["git","sparse-checkout","init","--no-cone"], cwd=td)
            open(os.path.join(td,".git","info","sparse-checkout"),"w").write("\n".join("/"+i for i,_,_ in want))
            r = run(["git","checkout","--quiet",commit], cwd=td, timeout=600)
            if r.returncode != 0:
                return ("CHECKOUT_FAIL", 0, [], time.time()-t0)
        dest = os.path.join(EX, org, repo)
        results_missing=[f for *_ ,f in gone]; results_modified=[]
        for inner, sha, fid in want:
            src = os.path.join(td, inner)
            if not os.path.exists(src): results_missing.append(fid); continue
            h = hashlib.sha256(open(src,"rb").read()).hexdigest()
            if h != sha: results_modified.append(fid); continue
            # 참조 해석 → sparse set 확장 → 추가 checkout
            rf = refs_for(src, tbase)
            mtls=[x for x in rf if x.lower().endswith(".mtl")]
            if rf:
                sc=os.path.join(td,".git","info","sparse-checkout")
                cur=set(open(sc).read().splitlines())
                new=cur | {"/"+x for x in rf}
                if new!=cur:
                    open(sc,"w").write("\n".join(sorted(new)))
                    run(["git","checkout","--quiet",commit], cwd=td, timeout=600)
            for m in mtls:
                mp=os.path.join(td,m)
                if os.path.exists(mp):
                    rf2=mtl_texrefs(mp, tbase)
                    if rf2:
                        sc=os.path.join(td,".git","info","sparse-checkout")
                        cur=set(open(sc).read().splitlines()); new=cur|{"/"+x for x in rf2}
                        if new!=cur:
                            open(sc,"w").write("\n".join(sorted(new)))
                            run(["git","checkout","--quiet",commit], cwd=td, timeout=600)
                        rf|=rf2
            for rel in rf:  # refs 먼저
                atomic_copy(os.path.join(td,rel), os.path.join(dest,rel))
            atomic_copy(src, os.path.join(dest,inner))  # mesh 마지막 = 완료 마커
            got+=1
        return ("OK", got, results_missing+results_modified, time.time()-t0)

def main():
    arg = sys.argv[1]; W = int(sys.argv[2]) if len(sys.argv)>2 else 32
    LIST = None
    if os.path.exists(arg) and not arg.isdigit():
        LIST = set(l.strip() for l in open(arg) if l.strip()); N = len(LIST)
    else:
        N = int(arg)
    md = pd.read_csv(f"{B}/metadata.csv", usecols=["sha256","file_identifier"])
    p = md.file_identifier.str.split("/")
    md["org"]=p.str[3]; md["repo"]=p.str[4]; md["commit"]=p.str[6]
    md["inner"]=p.str[7:].str.join("/")
    md["rel"]="raw/github/extracted/"+md.org+"/"+md.repo+"/"+md.inner
    skip=set()
    for fn in (MISS,MOD):
        if os.path.exists(fn): skip |= set(l.strip() for l in open(fn) if l.strip())
    have = md.rel.apply(lambda r: os.path.exists(os.path.join(B,r)))
    pool = md[~have & ~md.file_identifier.isin(skip)]
    todo = pool[pool.sha256.isin(LIST)] if LIST is not None else pool.head(N)
    print(f"[gh-partial] 미확보에서 {len(todo):,}개 선정 (workers={W})", flush=True)
    jobs={}
    for r in todo.itertuples():
        jobs.setdefault((r.org,r.repo,r.commit),[]).append((r.inner,r.sha256,r.file_identifier))
    jobs=list(jobs.items())
    print(f"[gh-partial] repo {len(jobs):,}개", flush=True)
    done=fail=objs=0; t0=time.time()
    with Pool(W) as pool:
        for st,g,missfids,dt in pool.imap_unordered(process_repo, jobs):
            done+=1; objs+=g
            if st!="OK": fail+=1
            for f in missfids:
                with open(MISS,"a") as fh: fh.write(f+"\n")
            if done%50==0:
                el=time.time()-t0
                print(f"[{done}/{len(jobs)}] objs {objs} | {done/el*60:.1f} repo/min | {objs/el*60:.1f} obj/min | fail {fail}", flush=True)
    el=time.time()-t0
    print(f"완료: repo {done} (실패 {fail}) obj {objs} in {el/60:.1f}min → {done/el*60:.1f} repo/min, {objs/el*60:.1f} obj/min", flush=True)

if __name__=="__main__":
    main()
