# B' (조인 규칙): blend도 같은-폴더 대신 참조 텍스처 문자열 스캔
import os, re, json, zipfile, shutil
import pandas as pd
RP="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/raw/github/repos"
Z=f"{RP}/caleb-long19/The-Hallowed_VR_Project.zip"
OUT="/workspace/jh/extract_preview/B2_strict/caleb-long19__The-Hallowed_VR_Project"
shutil.rmtree(OUT, ignore_errors=True)
md=pd.read_csv("/workspace/jh/trellis500k/datasets/ObjaverseXL_github/metadata.csv", usecols=["file_identifier"])
want=[f.split("/",7)[7] for f in md.file_identifier if "github.com/caleb-long19/The-Hallowed_VR_Project/" in f]
zf=zipfile.ZipFile(Z); info={i.filename:i.file_size for i in zf.infolist() if not i.filename.endswith("/")}
lower={n.lower():n for n in info}; base={}
for n in info: base.setdefault(os.path.basename(n).lower(),[]).append(n)
TEXRE=re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)
sel=set()
for w in want:
    n=lower.get(w.lower());
    if n is None: continue
    sel.add(n); ext=n.rsplit(".",1)[-1].lower()
    if ext in ("fbx","blend"):
        for m in TEXRE.findall(zf.read(n)):
            bn=os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore").lower()
            sel |= set(base.get(bn,[]))
for n in sel:
    p=os.path.join(OUT,n); os.makedirs(os.path.dirname(p),exist_ok=True)
    open(p,"wb").write(zf.read(n))
tot=sum(info[n] for n in sel)
print(f"매칭 mesh: {len(want)}개")
print(f"B (기존, 폴더 규칙): 128개 55.8MB")
print(f"B'(조임, 참조만):    {len(sel)}개 {tot/1e6:.1f}MB")
exts={}
for n in sel:
    e=n.rsplit(".",1)[-1].lower(); exts[e]=exts.get(e,0)+1
print("B' 구성:", dict(sorted(exts.items(), key=lambda x:-x[1])))
