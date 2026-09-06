# TEX_MISSING 표본을 원천 트리와 대조: 참조 텍스처가 repo 트리에 존재? (C=우리 누락) or 부재? (B=원천 부재)
import os, re, json, struct, random, subprocess, tempfile
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"; SH=f"{B}/shards/shard1"
ENV=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/workspace/jh/.gh_askpass")
TEXRE=re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)
df=pd.read_csv(f"{SH}.csv"); random.seed(7)
md=pd.read_csv(f"{B}/metadata.csv", usecols=["file_identifier"])
commit={}
for f in md.file_identifier:
    pp=f.split("/")
    if len(pp)>=8: commit[(pp[3],pp[4])]=pp[6]
# TEX_MISSING 후보 다시 찾기 (fbx/obj/blend 각 15개)
def refs_of(p,ext,dp):
    data=open(p,"rb").read()
    if ext=="obj":
        return [m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$", data.decode("utf8","ignore"))]
    return [os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore") for m in TEXRE.findall(data)]
cases={"fbx":[],"obj":[],"blend":[]}
for rel in df.sample(8000, random_state=7).shard_path:
    ext=rel.rsplit(".",1)[-1].lower()
    if ext not in cases or len(cases[ext])>=15: continue
    p=os.path.join(SH,rel); dp=os.path.dirname(p)
    if not os.path.exists(p): continue
    try: refs=refs_of(p,ext,dp)
    except Exception: continue
    if not refs: continue
    repo_root=os.path.join(SH, rel.split("/")[0])
    have=set()
    for dp2,_,fs2 in os.walk(repo_root):
        for f2 in fs2: have.add(f2.lower())
    missing=[r for r in refs if os.path.basename(r).lower() not in have]
    if missing: cases[ext].append((rel, missing[:3]))
    if all(len(v)>=15 for v in cases.values()): break
src_has=src_no=clone_fail=0
for ext,lst in cases.items():
    for rel,missing in lst:
        org,repo=rel.split("/")[0].split("__",1); c=commit.get((org,repo))
        if not c: continue
        with tempfile.TemporaryDirectory() as td:
            r=subprocess.run(["git","clone","--depth","1","--filter=blob:none","--no-checkout","--quiet",f"https://github.com/{org}/{repo}.git",td],env=ENV,capture_output=True,timeout=120)
            if r.returncode!=0: clone_fail+=1; continue
            t=subprocess.run(["git","-c","core.quotepath=false","ls-tree","-r","--name-only",c],cwd=td,env=ENV,capture_output=True,timeout=60)
            tree=set(os.path.basename(x).lower() for x in t.stdout.decode("utf8","ignore").splitlines())
        found=any(os.path.basename(m).lower() in tree for m in missing)
        if found: src_has+=1
        else: src_no+=1
print(f"TEX_MISSING 표본 {src_has+src_no}건 원천 대조:")
print(f"  원천 트리에 존재(=우리 누락 C): {src_has}")
print(f"  원천에도 없음(=원본 부재 B):   {src_no}")
print(f"  (clone 실패 제외 {clone_fail})")
