# Phase A — 배선 좌표 보강: fbx_material_name(externalObjects) + gameobject_name(prefab)
# 텍스처 다운로드 0. 대상 = slotscan 결과 좌표가 없거나 무력한 확정 mesh
# env: PA_WORKERS(16) PA_TMULT(1)
import os, re, sys, csv, glob, time, shutil, subprocess
from multiprocessing import Pool
from collections import defaultdict
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
TMP = "/workspace/jh/pa_tmp"; DONE = "/workspace/jh/phase_a/.done"
GUID = re.compile(r"guid:\s*([0-9a-f]{32})")
TM = float(os.environ.get("PA_TMULT", "1"))
ENV = dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")

def dec(x):
    # Unity YAML의 비ASCII 이름은 escape 형태로 저장됨 -> 원문 복원
    x = x.strip()
    if len(x) >= 2 and x[0] == x[-1] == '"': x = x[1:-1]
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), x).strip()

def run(cmd, timeout, cwd=None, input=None):
    return subprocess.run(cmd, env=ENV, timeout=timeout*TM, cwd=cwd,
                          capture_output=True, text=True, errors="replace", input=input)

def build_tasks():
    # slotscan → 대상 sha
    need = set()
    for f in glob.glob("/workspace/jh/slotscan/part_*.csv"):
        for r in csv.reader(open(f)):
            if not r or r[2].startswith("IMPORT"): continue
            if not (r[1] == "HAS_SLOT" and r[2] == "FIT"): need.add(r[0])
    # metadata → fileIdentifier
    fid = {}
    with open(f"{B}/metadata.csv", encoding="utf8", errors="ignore") as fh:
        for r in csv.DictReader(fh):
            if r["sha256"] in need: fid[r["sha256"]] = r["file_identifier"]
    sp = {}
    with open(f"{B}/shards/shard1_confirmed_map.csv") as fh:
        for r in csv.DictReader(fh):
            if r["sha256"] in need: sp[r["sha256"]] = r["shard_path"]
    tasks = {}
    for sha in need:
        f = str(fid.get(sha, ""))
        if "github.com" not in f: continue
        p = f.split("github.com/")[1].split("/")
        if len(p) < 5: continue
        key = f"{p[0]}__{p[1]}"
        tasks.setdefault(key, {"org": p[0], "repo": p[1], "items": []})["items"].append(
            (sha, sp.get(sha, ""), p[3], "/".join(p[4:])))
    return tasks

def parse_prefab(txt, meshguid, g2p):
    """returns [(gameobject_name, slot_index, mat_path)]"""
    out = []
    docs = re.split(r"^--- !u!", txt, flags=re.M)
    go_name = {}; go_hasmesh = set(); renders = []
    for d in docs:
        head = d.split("\n", 1)[0]
        t = head.split(" ", 1)[0]
        fidm = re.search(r"&(\d+)", head)
        did = fidm.group(1) if fidm else ""
        if t == "1":
            m = re.search(r"m_Name:\s*(.*)", d)
            if m: go_name[did] = dec(m.group(1))
        gm = re.search(r"m_GameObject:\s*\{fileID:\s*(\d+)", d)
        go = gm.group(1) if gm else ""
        if t == "33" and meshguid in d and go: go_hasmesh.add(go)
        if t == "137" and meshguid in d and go:
            arr = re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)", d)
            if arr: renders.append((go, arr.group(1)))
        if t == "23" and go:
            arr = re.search(r"m_Materials:\s*\n((?:\s*-\s*\{[^}]*\}\s*\n)+)", d)
            if arr: renders.append((go, arr.group(1), True))
    for r in renders:
        go, arrtxt = r[0], r[1]
        if len(r) == 3 and go not in go_hasmesh: continue   # MeshRenderer는 같은 GO의 MeshFilter 확인
        for i, ref in enumerate(re.findall(r"\{[^}]*\}", arrtxt)):
            g = GUID.search(ref)
            if g and g2p.get(g.group(1), "").endswith(".mat"):
                out.append((go_name.get(go, ""), i, g2p[g.group(1)]))
    return out

def process(arg):
    key, t = arg
    rd = os.path.join(TMP, key); rows = []
    def flush():
        with open(f"{DONE}/{key}.csv.tmp", "w", newline="") as fh: csv.writer(fh).writerows(rows)
        os.replace(f"{DONE}/{key}.csv.tmp", f"{DONE}/{key}.csv")
        shutil.rmtree(rd, ignore_errors=True)
    try:
        time.sleep(0.2)
        r = run(["git", "clone", "--filter=blob:none", "--no-checkout", "--quiet",
                 f"https://github.com/{t['org']}/{t['repo']}.git", rd], 600)
        if r.returncode != 0:
            rows = [[it[0], it[1], key, "CLONE_FAIL", "", "", "", ""] for it in t["items"]]; flush(); return key
        run(["git", "-C", rd, "sparse-checkout", "set", "--no-cone", "*.meta", "*.prefab", "*.unity"], 300)
        for commit in sorted(set(it[2] for it in t["items"])):
            co = run(["git", "-C", rd, "checkout", "--quiet", "--force", commit], 1800)
            if co.returncode != 0:
                rows += [[it[0], it[1], key, "CHECKOUT_FAIL", "", "", "", ""] for it in t["items"] if it[2] == commit]
                continue
            g2p = {}
            for mp in glob.glob(f"{rd}/**/*.meta", recursive=True):
                m = GUID.search(open(mp, encoding="utf8", errors="ignore").read(4096))
                if m: g2p[m.group(1)] = os.path.relpath(mp, rd)[:-5]
            scenes = [s for s in glob.glob(f"{rd}/**/*.prefab", recursive=True) +
                      glob.glob(f"{rd}/**/*.unity", recursive=True) if os.path.getsize(s) <= 20_000_000]
            for sha, shp, cm, inner in [it for it in t["items"] if it[2] == commit]:
                mm = os.path.join(rd, inner + ".meta")
                if not os.path.exists(mm):
                    rows.append([sha, shp, key, "NO_MESH_META", "", "", "", ""]); continue
                txt = open(mm, encoding="utf8", errors="ignore").read()
                mg = GUID.search(txt)
                meshguid = mg.group(1) if mg else ""
                # (a) externalObjects: fbx 재질 이름 → .mat
                got = 0
                blk = re.search(r"externalObjects:\s*\n(.*?)\n  \w", txt, re.S)
                if blk:
                    for nm, gd in re.findall(
                            r"type: UnityEngine:Material\s*\n\s*assembly:[^\n]*\n\s*name:\s*(.+?)\n\s*second:\s*\{[^}]*guid:\s*([0-9a-f]{32})",
                            blk.group(1)):
                        mp2 = g2p.get(gd, "")
                        if mp2.endswith(".mat"):
                            rows.append([sha, shp, key, "FBXMAT", "", dec(nm), mp2, ""]); got += 1
                # (b) prefab/씬: GameObject 이름 + 슬롯 번호
                if meshguid:
                    seen = set()
                    for sf in scenes:
                        s2 = open(sf, encoding="utf8", errors="ignore").read()
                        if meshguid not in s2: continue
                        for goname, si, mp2 in parse_prefab(s2, meshguid, g2p):
                            k = (goname, si, mp2)
                            if k in seen: continue
                            seen.add(k)
                            rows.append([sha, shp, key, "GO", si, goname, mp2, os.path.basename(sf)]); got += 1
                if got == 0:
                    rows.append([sha, shp, key, "NO_COORD", "", "", "", ""])
                # mesh.meta 원본 보관 (수 KB)
                dst = os.path.join("/workspace/jh/phase_a/meta", key, inner + ".meta")
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try: shutil.copy2(mm, dst)
                except Exception: pass
        flush()
    except Exception as e:
        rows = [[it[0], it[1], key, f"ERR:{type(e).__name__}", "", "", "", ""] for it in t["items"]]
        flush()
    return key

if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True); os.makedirs(DONE, exist_ok=True)
    os.makedirs("/workspace/jh/phase_a/meta", exist_ok=True)
    tasks = build_tasks()
    todo = [(k, v) for k, v in sorted(tasks.items()) if not os.path.exists(f"{DONE}/{k}.csv")]
    print(f"대상 repo {len(tasks)} / 신규 {len(todo)} / mesh {sum(len(v['items']) for v in tasks.values())}", flush=True)
    W = int(os.environ.get("PA_WORKERS", "16"))
    t0 = time.time(); n = 0
    with Pool(W) as p:
        for _ in p.imap_unordered(process, todo, chunksize=1):
            n += 1
            if n % 100 == 0:
                el = time.time() - t0
                print(f"{n}/{len(todo)} ({n/el*60:.0f} repo/min, ETA {(len(todo)-n)*el/n/3600:.1f}h)", flush=True)
    acc = []
    for f in glob.glob(f"{DONE}/*.csv"): acc += list(csv.reader(open(f)))
    out = f"{B}/shards/shard1_binding_coords.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sha256", "shard_path", "repo", "coord_type", "slot_index", "name", "mat_path", "source_file"])
        w.writerows(acc)
    from collections import Counter
    c = Counter(r[3] for r in acc)
    print(f"\n총 {len(acc)}행 / mesh {len(set(r[0] for r in acc))}")
    for k, v in c.most_common(): print(f"  {k:16s} {v}")
    solved = set(r[0] for r in acc if r[3] in ("FBXMAT", "GO"))
    allm = set(r[0] for r in acc)
    print(f"\n좌표 확보: {len(solved)} / {len(allm)} ({len(solved)/max(len(allm),1)*100:.0f}%)")
