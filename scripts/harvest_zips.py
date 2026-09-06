# 기존 repo zip → B'-strict 추출 (매칭 파일 sha256 검증 + 참조 동반) → 성공 zip 목록 기록
import os, re, json, zipfile, hashlib, sys
from multiprocessing import Pool
import pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
RP=f"{B}/raw/github/repos"; EX=f"{B}/raw/github/extracted"
md=pd.read_csv(f"{B}/metadata.csv", usecols=["sha256","file_identifier"])
p=md.file_identifier.str.split("/")
md["org"]=p.str[3]; md["repo"]=p.str[4]; md["inner"]=p.str[7:].str.join("/")
by_repo={}
for r in md.itertuples():
    by_repo.setdefault((r.org,r.repo),[]).append((r.inner,r.sha256))
TEXRE=re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)

def atomic_write(dst, data):
    if os.path.exists(dst): return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    t=dst+".copytmp"
    with open(t,"wb") as f: f.write(data)
    os.replace(t,dst)

def harvest(zpath):
    org,repo=zpath.split("/")[-2], zpath.split("/")[-1][:-4]
    want=by_repo.get((org,repo),[])
    try: zf=zipfile.ZipFile(zpath)
    except Exception: return (zpath,"BADZIP",0,0)
    names={i.filename for i in zf.infolist() if not i.filename.endswith("/")}
    lower={n.lower():n for n in names}; base={}
    for n in names: base.setdefault(os.path.basename(n).lower(),[]).append(n)
    got=miss=0
    dest=os.path.join(EX,org,repo)
    for inner,sha in want:
        n=lower.get(inner.lower())
        if n is None: miss+=1; continue
        data=zf.read(n)
        if hashlib.sha256(data).hexdigest()!=sha: miss+=1; continue
        atomic_write(os.path.join(dest,inner), data); got+=1
        ext=inner.rsplit(".",1)[-1].lower()
        refs=set()
        try:
            if ext=="obj":
                txt=data.decode("utf8","ignore")
                for mtl in re.findall(r"(?im)^mtllib\s+(.+)$", txt):
                    for x in base.get(os.path.basename(mtl.strip()).lower(),[]):
                        refs.add(x)
                        mt=zf.read(x).decode("utf8","ignore")
                        for tex in re.findall(r"(?im)^map_\w+\s+(.+)$", mt):
                            refs.update(base.get(os.path.basename(tex.strip().split()[-1]).lower(),[]))
            elif ext=="gltf":
                g=json.loads(data)
                for sec in ("buffers","images"):
                    for it in g.get(sec,[]):
                        u=it.get("uri","")
                        if u and not u.startswith("data:"): refs.update(base.get(os.path.basename(u).lower(),[]))
            elif ext=="dae":
                for tex in re.findall(r"<init_from>([^<]+)</init_from>", data.decode("utf8","ignore")):
                    refs.update(base.get(os.path.basename(tex.strip()).lower(),[]))
            elif ext in ("fbx","blend"):
                for m in TEXRE.findall(data):
                    refs.update(base.get(os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore").lower(),[]))
        except Exception: pass
        for r_ in refs:
            try: atomic_write(os.path.join(dest,r_), zf.read(r_))
            except Exception: pass
    return (zpath,"OK",got,miss)

zips=[os.path.join(dp,f) for dp,_,fs in os.walk(RP) for f in fs if f.endswith(".zip")]
print(f"수확 대상 zip: {len(zips)}")
with Pool(24) as p: rs=p.map(harvest, zips)
ok=[r for r in rs if r[1]=="OK"]; bad=[r for r in rs if r[1]=="BADZIP"]
tg=sum(r[2] for r in ok); tm=sum(r[3] for r in ok)
print(f"완료: zip {len(ok)}개 정상 (object 추출 {tg}, sha불일치/부재 {tm}) / 깨진 zip {len(bad)}개")
with open("/workspace/jh/harvested_zips.txt","w") as f:
    for r in ok: f.write(r[0]+"\n")
with open("/workspace/jh/harvest_badzips.txt","w") as f:
    for r in bad: f.write(r[0]+"\n")
