# 통합 회수 v3 — 텍스처 회수 + 배선 좌표를 repo 1회 방문에 동시 수집 (Unity 전용)
# usage: python recover_v3.py <shard>        예: python recover_v3.py shard2
# env: RV_WORKERS(16) RV_TMULT(1) RV_KEYS(repo 목록 파일로 대상 제한)
import os, re, sys, csv, glob, time, shutil, subprocess
from multiprocessing import Pool
from collections import defaultdict

SHARD = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else "shard2"
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
OUT = f"{B}/unity_confirmed_{SHARD}"
DONE = f"{OUT}/.done"
TMP = f"/workspace/jh/rv_tmp_{SHARD}"
IMG = (".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
BUCKETS = {"TEX_MISSING","NO_REF_OR_EMBEDDED","TEX_PARTIAL","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"}
GUID = re.compile(r"guid:\s*([0-9a-f]{32})")
SLOTRE = re.compile(r"-\s+(\w+):\s*\n\s+m_Texture:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
COLRE = re.compile(r"_Color:\s*\{r:\s*([\d.eE+-]+),\s*g:\s*([\d.eE+-]+),\s*b:\s*([\d.eE+-]+),\s*a:\s*([\d.eE+-]+)")
EXTOBJ = re.compile(r"type: UnityEngine:Material\s*\n\s*assembly:[^\n]*\n\s*name:\s*(.+?)\n\s*second:\s*\{[^}]*guid:\s*([0-9a-f]{32})")
TM = float(os.environ.get("RV_TMULT", "1"))
ENV = dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")

def dec(x):
    # Unity YAML의 비ASCII 이름은 escape 형태로 저장됨 -> 원문 복원
    x = x.strip()
    if len(x) >= 2 and x[0] == x[-1] == '"': x = x[1:-1]
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), x).strip()

def run(cmd, timeout, cwd=None, input=None):
    return subprocess.run(cmd, env=ENV, timeout=timeout*TM, cwd=cwd,
                          capture_output=True, text=True, errors="replace", input=input)

def esc(p): return "/" + re.sub(r"([\[\]*?])", r"\\\1", p)

def build_tasks():
    import pandas as pd
    st = pd.read_csv(f"{B}/shards/{SHARD}_texture_status_v2.csv")
    st = st[st.tex_status.isin(BUCKETS)]
    md = pd.read_csv(f"{B}/metadata.csv", usecols=["sha256", "file_identifier"])
    fid = dict(zip(md.sha256, md.file_identifier))
    tasks = {}
    for r in st.itertuples(index=False):
        f = str(fid.get(r.sha256, ""))
        if "github.com" not in f: continue
        p = f.split("github.com/")[1].split("/")
        if len(p) < 5: continue
        key = f"{p[0]}__{p[1]}"
        tasks.setdefault(key, {"org": p[0], "repo": p[1], "items": []})["items"].append(
            (r.sha256, r.tex_status, r.shard_path, p[3], "/".join(p[4:])))
    return tasks

def parse_scene(txt, meshguid, g2p):
    """prefab/씬 → [(gameobject_name, slot_index, mat_path)]"""
    out = []
    docs = re.split(r"^--- !u!", txt, flags=re.M)
    go_name, has_mesh, renders = {}, set(), []
    for d in docs:
        head = d.split("\n", 1)[0]
        t = head.split(" ", 1)[0]
        idm = re.search(r"&(\d+)", head)
        did = idm.group(1) if idm else ""
        if t == "1":
            m = re.search(r"m_Name:\s*(.*)", d)
            if m: go_name[did] = dec(m.group(1))
        gm = re.search(r"m_GameObject:\s*\{fileID:\s*(\d+)", d)
        go = gm.group(1) if gm else ""
        if t == "33" and meshguid in d and go: has_mesh.add(go)
        if t == "137" and meshguid in d and go:
            arr = re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)", d)
            if arr: renders.append((go, arr.group(1), False))
        if t == "23" and go:
            arr = re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)", d)
            if arr: renders.append((go, arr.group(1), True))
    for go, arrtxt, need_filter in renders:
        if need_filter and go not in has_mesh: continue
        for i, ref in enumerate(re.findall(r"\{[^}]*\}", arrtxt)):
            g = GUID.search(ref)
            if g and g2p.get(g.group(1), "").endswith(".mat"):
                out.append((go_name.get(go, ""), i, g2p[g.group(1)]))
    return out

def process(arg):
    key, t = arg
    rd = os.path.join(TMP, key)
    res, files, mp = [], [], []
    def flush():
        for suf, data in ((".csv", res), (".files.csv", files), (".map.csv", mp)):
            with open(f"{DONE}/{key}{suf}.tmp", "w", newline="") as fh: csv.writer(fh).writerows(data)
            os.replace(f"{DONE}/{key}{suf}.tmp", f"{DONE}/{key}{suf}")
        shutil.rmtree(rd, ignore_errors=True)
    try:
        # ── clone (백오프 재시도 3회) ──
        ok = False
        for attempt in range(3):
            shutil.rmtree(rd, ignore_errors=True)
            time.sleep(0.2 + attempt * 3)
            r = run(["git", "clone", "--filter=blob:none", "--no-checkout", "--quiet",
                     f"https://github.com/{t['org']}/{t['repo']}.git", rd], 600)
            if r.returncode == 0: ok = True; break
            if "not found" in (r.stderr or "").lower() or "404" in (r.stderr or ""): break
        if not ok:
            res = [[i[0], i[1], i[2], "CLONE_FAIL", 0, 0, 0, ""] for i in t["items"]]; flush(); return key
        run(["git", "-C", rd, "sparse-checkout", "set", "--no-cone", "*.meta", "*.mat", "*.prefab", "*.unity"], 300)

        for commit in sorted(set(i[3] for i in t["items"])):
            mine = [i for i in t["items"] if i[3] == commit]
            co = run(["git", "-C", rd, "checkout", "--quiet", "--force", commit], 1800)
            if co.returncode != 0:
                res += [[i[0], i[1], i[2], "CHECKOUT_FAIL", 0, 0, 0, ""] for i in mine]; continue
            tree = set(run(["git", "-C", rd, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", commit], 600).stdout.splitlines())
            if not any(x.endswith(".meta") for x in tree):
                res += [[i[0], i[1], i[2], "NO_UNITY", 0, 0, 0, ""] for i in mine]; continue

            g2p = {}
            for f2 in glob.glob(f"{rd}/**/*.meta", recursive=True):
                m = GUID.search(open(f2, encoding="utf8", errors="ignore").read(4096))
                if m: g2p[m.group(1)] = os.path.relpath(f2, rd)[:-5]
            scenes = [s for s in glob.glob(f"{rd}/**/*.prefab", recursive=True) +
                      glob.glob(f"{rd}/**/*.unity", recursive=True) if os.path.getsize(s) <= 20_000_000]
            matcache = {}
            def matinfo(rel):
                if rel not in matcache:
                    fp = os.path.join(rd, rel)
                    if not os.path.exists(fp): matcache[rel] = ([], 1.0)
                    else:
                        txt = open(fp, encoding="utf8", errors="ignore").read()
                        cm = COLRE.search(txt)
                        matcache[rel] = (SLOTRE.findall(txt), float(cm.group(4)) if cm else 1.0)
                return matcache[rel]

            need, pend = set(), []
            for sha, bucket, shp, cm2, inner in mine:
                mmp = os.path.join(rd, inner + ".meta")
                if not os.path.exists(mmp):
                    res.append([sha, bucket, shp, "NO_MESH_META", 0, 0, 0, ""]); continue
                mtxt = open(mmp, encoding="utf8", errors="ignore").read()
                mg = GUID.search(mtxt)
                meshguid = mg.group(1) if mg else ""
                # ① mesh.meta externalObjects → (fbx 재질 이름, mat)
                binds, src = [], set()
                blk = re.search(r"externalObjects:\s*\n(.*?)\n  \w", mtxt, re.S)
                if blk:
                    for nm, gd in EXTOBJ.findall(blk.group(1)):
                        mp2 = g2p.get(gd, "")
                        if mp2.endswith(".mat"):
                            binds.append(("META", "", dec(nm), "", mp2)); src.add("META")
                # ② prefab/씬 → (GameObject 이름, 슬롯, mat)
                if meshguid:
                    seen = set()
                    for sf in scenes:
                        s2 = open(sf, encoding="utf8", errors="ignore").read()
                        if meshguid not in s2: continue
                        for gname, si, mp2 in parse_scene(s2, meshguid, g2p):
                            k2 = (gname, si, mp2)
                            if k2 in seen: continue
                            seen.add(k2); binds.append(("PREFAB", si, "", gname, mp2)); src.add("PREFAB")
                if not binds:
                    res.append([sha, bucket, shp, "NO_RECORD", 0, 0, 0, ""]); continue
                source = "+".join(sorted(src))
                # ③ 재질 → 슬롯별 텍스처
                texrows, absent = [], 0
                for bsrc, si, fbxnm, gonm, matrel in binds:
                    slots, alpha = matinfo(matrel)
                    for ts, g in slots:
                        tp = g2p.get(g, "")
                        if not tp.lower().endswith(IMG): continue
                        if tp in tree:
                            texrows.append((bsrc, si, fbxnm, gonm, matrel, ts, tp, alpha)); need.add(tp)
                        else: absent += 1
                if not texrows:
                    res.append([sha, bucket, shp, f"{source}_{'TEX_ABSENT' if absent else 'COLORS_ONLY'}",
                                len(binds), 0, 0, ""]); continue
                pend.append((sha, bucket, shp, source, len(binds), texrows, absent))

            # ④ 텍스처만 추가 checkout → 복사
            if need:
                pats = ["*.meta", "*.mat", "*.prefab", "*.unity"] + [esc(p) for p in sorted(need)]
                run(["git", "-C", rd, "sparse-checkout", "set", "--no-cone", "--stdin"], 900, input="\n".join(pats))
                run(["git", "-C", rd, "checkout", "--quiet", "--force", commit], 1800)
                copied = set()
                for p2 in sorted(need):
                    src2 = os.path.join(rd, p2)
                    if not os.path.exists(src2): continue
                    dst = os.path.join(OUT, key, p2)
                    if not os.path.exists(dst):
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src2, dst + ".tmp"); os.replace(dst + ".tmp", dst)
                        files.append([key, p2, os.path.getsize(dst)])
                    copied.add(p2)
                for sha, bucket, shp, source, nb, texrows, absent in pend:
                    got = 0
                    for bsrc, si, fbxnm, gonm, matrel, ts, tp, alpha in texrows:
                        d = 1 if tp in copied else 0; got += d
                        mp.append([sha, shp, key, bsrc, si, fbxnm, gonm, matrel, ts, tp, alpha, d])
                    # 라벨은 결과물 검사 후 부여
                    res.append([sha, bucket, shp, f"{source}_{'CONFIRMED' if got else 'TEX_ABSENT'}",
                                nb, len(texrows), got,
                                "ALPHA0" if any(x[7] == 0 for x in texrows) else ""])
        flush()
    except Exception as e:
        res = [[i[0], i[1], i[2], f"ERR:{type(e).__name__}", 0, 0, 0, ""] for i in t["items"]]
        flush()
    return key

if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True); os.makedirs(DONE, exist_ok=True)
    tasks = build_tasks()
    keys = sorted(tasks)
    kf = os.environ.get("RV_KEYS", "")
    if kf:
        want = set(open(kf).read().split()); keys = [k for k in keys if k in want]
    lim = next((int(a) for a in sys.argv[2:] if a.isdigit()), 0)
    if lim: keys = keys[:lim]
    todo = [(k, tasks[k]) for k in keys if not os.path.exists(f"{DONE}/{k}.csv")]
    tot_mesh = sum(len(tasks[k]["items"]) for k in keys)
    print(f"[{SHARD}] 대상 repo {len(keys):,} / 신규 {len(todo):,} / mesh {tot_mesh:,}", flush=True)
    W = int(os.environ.get("RV_WORKERS", "16"))
    t0 = time.time(); n = 0
    with Pool(W) as p:
        for _ in p.imap_unordered(process, todo, chunksize=1):
            n += 1
            if n % 200 == 0:
                el = time.time() - t0
                print(f"{n:,}/{len(todo):,} ({n/el*60:.0f} repo/min, ETA {(len(todo)-n)*el/n/3600:.1f}h)", flush=True)

    def merge(suf, hdr, name):
        acc = []
        for f2 in glob.glob(f"{DONE}/*{suf}"):
            if suf == ".csv" and (f2.endswith(".files.csv") or f2.endswith(".map.csv")): continue
            acc += list(csv.reader(open(f2)))
        with open(f"{B}/shards/{name}", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(hdr); w.writerows(acc)
        return acc
    R = merge(".csv", ["sha256","bucket","shard_path","result","n_binds","n_slot_tex","n_tex_dl","flags"],
              f"{SHARD}_confirmed_results.csv")
    F = merge(".files.csv", ["repo","path","bytes"], f"{SHARD}_confirmed_files.csv")
    M = merge(".map.csv", ["sha256","mesh_path","repo","source","slot_index","fbx_material_name",
                           "gameobject_name","mat_path","tex_slot","texture_path","mat_alpha","downloaded"],
              f"{SHARD}_confirmed_map.csv")

    # ── 불변식 검사 ──
    bad1 = [r for r in R if r[3].endswith("_CONFIRMED") and int(r[6]) <= 0]
    bad2 = [r for r in R if r[3].endswith("_TEX_ABSENT") and int(r[6]) > 0]
    import random
    okm = [r for r in M if r[11] == "1"]
    samp = random.sample(okm, min(200, len(okm))) if okm else []
    miss = sum(0 if os.path.exists(os.path.join(OUT, r[2], r[9])) else 1 for r in samp)
    from collections import Counter
    c = Counter(r[3] for r in R)
    conf = sum(v for k, v in c.items() if k.endswith("_CONFIRMED"))
    col = sum(v for k, v in c.items() if k.endswith("_COLORS_ONLY"))
    nouni = c.get("NO_UNITY", 0)
    tot = len(R)
    print("\n" + "="*54)
    print(f"[{SHARD}] 회수 결과 — 깔때기")
    print("="*54)
    print(f"  회수 대상 (5버킷)          {tot:8,}")
    print(f"  ├─ Unity 아님 (시도 불가)   {nouni:8,} ({nouni/tot*100:4.1f}%)")
    print(f"  ├─ ✅ 확정 + 텍스처 확보    {conf:8,} ({conf/tot*100:4.1f}%)")
    print(f"  ├─ ✅ 확정 + 단색이 정답    {col:8,} ({col/tot*100:4.1f}%)")
    for k, v in c.most_common():
        if not (k.endswith("_CONFIRMED") or k.endswith("_COLORS_ONLY") or k == "NO_UNITY"):
            print(f"  ├─ ❌ {k:22s} {v:8,}")
    print(f"  └─ 텍스처 파일             {len(F):8,} 개")
    print(f"\n  좌표 동시 수집: 이름 {sum(1 for r in M if r[5] or r[6]):,}행 / 전체 {len(M):,}행")
    print(f"\n== 불변식 검사 ==")
    print(f"  CONFIRMED인데 0장: {len(bad1)} | TEX_ABSENT인데 >0: {len(bad2)} | 맵표본 실물없음: {miss}")
    print("  PASS" if not (bad1 or bad2 or miss) else "  FAIL — 확인 필요")
