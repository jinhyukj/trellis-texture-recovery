# NO_REF / TEX_MISSING 표본: 원천 repo 트리에서 mesh 주변(같은 폴더·인근)에 이미지 파일이 있는지 대조
import os, subprocess, random, csv, shutil, sys
import pandas as pd
SH="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/shards/shard1"
META="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/metadata.csv"
ST="/workspace/jh/shard1_texture_status.csv"
TMP="/workspace/jh/nearby_tmp"
IMG=(".png",".jpg",".jpeg",".tga",".bmp",".tif",".tiff",".dds",".exr",".hdr",".webp",".psd")
env=dict(os.environ, GIT_ASKPASS="/workspace/jh/.gh_askpass", GIT_TERMINAL_PROMPT="0")
df=pd.read_csv(ST); md=pd.read_csv(META)
md=md[md.sha256.isin(df.sha256)]
fid=dict(zip(md.sha256, md.file_identifier))
random.seed(7)
out=[]
for bucket in ["NO_REF_OR_EMBEDDED","TEX_MISSING"]:
    sub=df[(df.tex_status==bucket)&df.ext.isin(["fbx","blend","obj","dae"])].sample(40, random_state=7)
    for _,r in sub.iterrows():
        f=fid.get(r.sha256,"")
        if "github.com" not in str(f): continue
        # fileIdentifier: https://github.com/org/repo/blob/<commit>/<path>
        parts=f.split("github.com/")[1].split("/")
        org,repo=parts[0],parts[1]; commit=parts[3]; inner="/".join(parts[4:])
        rd=os.path.join(TMP,f"{org}__{repo}")
        try:
            if not os.path.exists(rd):
                subprocess.run(["git","clone","--filter=blob:none","--no-checkout","--quiet",
                    f"https://github.com/{org}/{repo}.git",rd], env=env, timeout=180, check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ls=subprocess.run(["git","-C",rd,"-c","core.quotepath=false","ls-tree","-r","--name-only",commit],
                capture_output=True, text=True, timeout=120, env=env)
            files=ls.stdout.splitlines()
            if not files: out.append((bucket,r.sha256,"CLONE_FAIL",0,0)); continue
            imgs=[x for x in files if x.lower().endswith(IMG)]
            mdir=os.path.dirname(inner)
            near=[x for x in imgs if os.path.dirname(x)==mdir or (mdir and x.startswith(mdir+"/"))]
            out.append((bucket,r.sha256,"OK",len(near),len(imgs)))
        except Exception:
            out.append((bucket,r.sha256,"CLONE_FAIL",0,0))
        sys.stdout.write("."); sys.stdout.flush()
shutil.rmtree(TMP, ignore_errors=True)
print()
with open("/workspace/jh/nearby_tex.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["bucket","sha256","status","imgs_near_mesh","imgs_in_repo"]); w.writerows(out)
for b in ["NO_REF_OR_EMBEDDED","TEX_MISSING"]:
    s=[o for o in out if o[0]==b and o[2]=="OK"]
    fails=len([o for o in out if o[0]==b and o[2]!="OK"])
    near=len([o for o in s if o[3]>0]); anyrepo=len([o for o in s if o[4]>0])
    print(f"{b}: 판정 {len(s)} (clone실패 {fails})")
    print(f"  mesh 폴더/하위에 이미지 존재: {near} ({near/max(len(s),1)*100:.0f}%)")
    print(f"  repo 어딘가에 이미지 존재:   {anyrepo} ({anyrepo/max(len(s),1)*100:.0f}%)")
