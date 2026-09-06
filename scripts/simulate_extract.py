# 기존 repo zip 표본으로 "파일 추출 모드" 용량 시뮬레이션
# 시나리오 A: 매칭 mesh 파일만 / B: + 참조 텍스처(정밀 파싱+fbx 근사) / C: + 같은 폴더 전체
import os, re, io, json, zipfile, sys
import pandas as pd
from multiprocessing import Pool

RP="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/raw/github/repos"
md=pd.read_csv("/workspace/jh/trellis500k/datasets/ObjaverseXL_github/metadata.csv", usecols=["file_identifier"])
md["key"]=md.file_identifier.str.extract(r"github\.com/([^/]+/[^/]+)/")[0]
md["inner"]=md.file_identifier.str.split("/").str[7:].str.join("/")
by_repo={}
for k,inner in zip(md.key, md.inner): by_repo.setdefault(k,[]).append(inner)

TEXEXT={"png","jpg","jpeg","tga","bmp","tif","tiff","dds","exr","hdr","webp","psd"}
def texname(s):
    m=re.findall(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', s, re.I)
    return {os.path.basename(x.replace(b"\\",b"/")).decode("utf8","ignore").lower() for x in m}

def analyze(zpath):
    org,repo=zpath.split("/")[-2], zpath.split("/")[-1][:-4]
    want=by_repo.get(f"{org}/{repo}",[])
    if not want: return None
    try: zf=zipfile.ZipFile(zpath)
    except Exception: return None
    info={i.filename:i.file_size for i in zf.infolist() if not i.filename.endswith("/")}
    lower={n.lower():n for n in info}
    base={}  # basename → 경로들
    for n in info: base.setdefault(os.path.basename(n).lower(),[]).append(n)
    A=set(); B=set(); C=set()
    for w in want:
        n = lower.get(w.lower())
        if n is None: continue
        A.add(n); B.add(n)
        d=os.path.dirname(n)
        for m2 in info:
            if os.path.dirname(m2)==d: C.add(m2)
        ext=n.rsplit(".",1)[-1].lower()
        try:
            if ext=="obj":
                txt=zf.read(n).decode("utf8","ignore")
                for mtl in re.findall(r"(?im)^mtllib\s+(.+)$", txt):
                    mn=base.get(os.path.basename(mtl.strip()).lower(),[])
                    for x in mn:
                        B.add(x)
                        mt=zf.read(x).decode("utf8","ignore")
                        for tex in re.findall(r"(?im)^map_\w+\s+(.+)$", mt):
                            for y in base.get(os.path.basename(tex.strip().split()[-1]).lower(),[]): B.add(y)
            elif ext=="gltf":
                g=json.loads(zf.read(n))
                for sec in ("buffers","images"):
                    for it in g.get(sec,[]):
                        u=it.get("uri","")
                        if u and not u.startswith("data:"):
                            for y in base.get(os.path.basename(u).lower(),[]): B.add(y)
            elif ext=="dae":
                txt=zf.read(n).decode("utf8","ignore")
                for tex in re.findall(r"<init_from>([^<]+)</init_from>", txt):
                    for y in base.get(os.path.basename(tex.strip()).lower(),[]): B.add(y)
            elif ext=="fbx":
                data=zf.read(n)
                for bn in texname(data):
                    for y in base.get(bn,[]): B.add(y)
            elif ext=="blend":
                d2=os.path.dirname(n)
                for m2 in info:
                    if os.path.dirname(m2)==d2: B.add(m2)
        except Exception: pass
    tot=sum(info.values())
    return (len(want), tot, sum(info[x] for x in A), sum(info[x] for x in B), sum(info[x] for x in C))

zips=[os.path.join(dp,f) for dp,_,fs in os.walk(RP) for f in fs if f.endswith(".zip")]
with Pool(24) as p: rs=[r for r in p.map(analyze, zips) if r]
import numpy as np
w=sum(r[0] for r in rs); tot=sum(r[1] for r in rs); a=sum(r[2] for r in rs); b=sum(r[3] for r in rs); c=sum(r[4] for r in rs)
print(f"표본: repo {len(rs)}개 / 매칭 object {w}개 / repo 원본 합 {tot/1e9:.1f}GB")
n_total_objects=311843
scale=n_total_objects/w
for name,v in [("A. mesh 파일만",a),("B. + 참조 텍스처(파싱)",b),("C. + 같은 폴더 전체",c),("(원안: repo 통짜)",tot)]:
    print(f"{name:26s} 표본 {v/1e9:7.1f}GB → 전체 외삽 {v*scale/1e12:6.2f}TB")
