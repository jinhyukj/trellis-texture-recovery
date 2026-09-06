# externalObjects의 name 이 fbx/obj 내부 재질 이름과 실제로 일치하는지 실측
# usage: blender -b --factory-startup -noaudio -P namecheck.py -- <N>
import bpy, os, sys, re, csv, glob, subprocess, shutil, random
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
D = f"{B}/unity_confirmed/.done"
TMP = "/workspace/jh/nc_tmp"
ENV = dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
N = int(sys.argv[sys.argv.index("--")+1])
GUID = re.compile(r"guid:\s*([0-9a-f]{32})")

rows = []
for f in glob.glob(D + "/*.csv"):
    if f.endswith((".files.csv", ".map.csv")): continue
    for r in csv.reader(open(f)):
        if len(r) > 3 and r[3] == "META_CONFIRMED":
            rows.append((r[0], r[2]))
random.seed(5); random.shuffle(rows)
rows = rows[:N*3]
want = set(x[0] for x in rows)

fid = {}
with open(f"{B}/metadata.csv", encoding="utf8", errors="ignore") as fh:
    rd = csv.DictReader(fh)
    for r in rd:
        if r["sha256"] in want: fid[r["sha256"]] = r["file_identifier"]

def blender_mats(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lo = path.lower()
    if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=path)
    elif lo.endswith(".obj"):
        try: bpy.ops.wm.obj_import(filepath=path)
        except AttributeError: bpy.ops.import_scene.obj(filepath=path)
    elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=path)
    else: raise RuntimeError("fmt")
    return set(re.sub(r"\.\d+$", "", m.name) for m in bpy.data.materials)

os.makedirs(TMP, exist_ok=True)
tally = {"EXACT": 0, "SUBSET": 0, "PARTIAL": 0, "NONE": 0, "SKIP": 0}
done = 0
for sha, sp in rows:
    if done >= N: break
    f = fid.get(sha, "")
    if "github.com" not in f: continue
    p = f.split("github.com/")[1].split("/")
    org, repo, commit, inner = p[0], p[1], p[3], "/".join(p[4:])
    rd = os.path.join(TMP, f"{org}__{repo}")
    try:
        if not os.path.exists(rd):
            subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--quiet",
                            f"https://github.com/{org}/{repo}.git", rd], env=ENV, timeout=400, check=True, capture_output=True)
            subprocess.run(["git", "-C", rd, "sparse-checkout", "set", "--no-cone", "*.meta"],
                           env=ENV, timeout=200, capture_output=True)
            subprocess.run(["git", "-C", rd, "checkout", "--quiet", "--force", commit],
                           env=ENV, timeout=900, capture_output=True)
        mm = os.path.join(rd, inner + ".meta")
        if not os.path.exists(mm): tally["SKIP"] += 1; continue
        txt = open(mm, encoding="utf8", errors="ignore").read()
        blk = re.search(r"externalObjects:\s*\n(.*?)\n  [a-zA-Z]", txt, re.S)
        names = re.findall(r"type: UnityEngine:Material\s*\n\s*assembly:[^\n]*\n\s*name:\s*(.+)",
                           blk.group(1) if blk else "")
        names = set(n.strip() for n in names)
        if not names: tally["SKIP"] += 1; continue
        bmats = blender_mats(os.path.join(B, "shards/shard1", sp))
        inter = names & bmats
        if names == bmats: k = "EXACT"
        elif names and names <= bmats: k = "SUBSET"
        elif inter: k = "PARTIAL"
        else: k = "NONE"
        tally[k] += 1; done += 1
        print(f"{k:8s} meta={sorted(names)[:3]} blender={sorted(bmats)[:3]}", flush=True)
    except Exception as e:
        tally["SKIP"] += 1
    finally:
        shutil.rmtree(rd, ignore_errors=True)
print("TALLY", tally)
