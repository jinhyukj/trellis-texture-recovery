# A/B/C 시나리오 실제 추출 미리보기 — 포맷 다양하게 repo 선별 (fbx/obj/glb/gltf/blend/dae)
import os, re, io, json, zipfile, time, shutil
import pandas as pd
RP="/workspace/jh/trellis500k/datasets/ObjaverseXL_github/raw/github/repos"
OUT="/workspace/jh/extract_preview"
shutil.rmtree(OUT, ignore_errors=True)
md=pd.read_csv("/workspace/jh/trellis500k/datasets/ObjaverseXL_github/metadata.csv", usecols=["file_identifier"])
md["key"]=md.file_identifier.str.extract(r"github\.com/([^/]+/[^/]+)/")[0]
md["inner"]=md.file_identifier.str.split("/").str[7:].str.join("/")
by_repo={}
for k,inner in zip(md.key, md.inner): by_repo.setdefault(k,[]).append(inner)

# 포맷별 대표 repo 찾기
want_ext=["fbx","obj","glb","gltf","blend","dae"]
picked={}
zips=[os.path.join(dp,f) for dp,_,fs in os.walk(RP) for f in fs if f.endswith(".zip")]
for z in zips:
    key="/".join([z.split("/")[-2], z.split("/")[-1][:-4]])
    inners=by_repo.get(key,[])
    for e in want_ext:
        if e in picked: continue
        if any(i.lower().endswith("."+e) for i in inners):
            picked[e]=z; break
    if len(picked)==len(want_ext): break
print("선택된 repo:", {e: p.split("/")[-1] for e,p in picked.items()})

TEXRE=re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)
def extract(zpath, scen, dst):
    org,repo=zpath.split("/")[-2], zpath.split("/")[-1][:-4]
    want=by_repo["/".join([org,repo])]
    zf=zipfile.ZipFile(zpath)
    info={i.filename:i.file_size for i in zf.infolist() if not i.filename.endswith("/")}
    lower={n.lower():n for n in info}
    base={}
    for n in info: base.setdefault(os.path.basename(n).lower(),[]).append(n)
    sel=set()
    for w in want:
        n=lower.get(w.lower())
        if n is None: continue
        sel.add(n)
        ext=n.rsplit(".",1)[-1].lower()
        if scen=="C":
            d=os.path.dirname(n)
            sel |= {m for m in info if os.path.dirname(m)==d}
        elif scen=="B":
            try:
                if ext=="obj":
                    txt=zf.read(n).decode("utf8","ignore")
                    for mtl in re.findall(r"(?im)^mtllib\s+(.+)$", txt):
                        for x in base.get(os.path.basename(mtl.strip()).lower(),[]):
                            sel.add(x)
                            mt=zf.read(x).decode("utf8","ignore")
                            for tex in re.findall(r"(?im)^map_\w+\s+(.+)$", mt):
                                sel |= set(base.get(os.path.basename(tex.strip().split()[-1]).lower(),[]))
                elif ext=="gltf":
                    g=json.loads(zf.read(n))
                    for sec in ("buffers","images"):
                        for it in g.get(sec,[]):
                            u=it.get("uri","")
                            if u and not u.startswith("data:"): sel |= set(base.get(os.path.basename(u).lower(),[]))
                elif ext=="dae":
                    for tex in re.findall(r"<init_from>([^<]+)</init_from>", zf.read(n).decode("utf8","ignore")):
                        sel |= set(base.get(os.path.basename(tex.strip()).lower(),[]))
                elif ext=="fbx":
                    for m in TEXRE.findall(zf.read(n)):
                        bn=os.path.basename(m.replace(b"\\",b"/")).decode("utf8","ignore").lower()
                        sel |= set(base.get(bn,[]))
                elif ext=="blend":
                    d=os.path.dirname(n); sel |= {m for m in info if os.path.dirname(m)==d}
            except Exception as e: print("  parse warn:", type(e).__name__)
    root=os.path.join(dst, f"{org}__{repo}")
    for n in sel:
        p=os.path.join(root, n); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p,"wb") as f: f.write(zf.read(n))
    return len(sel), sum(info[n] for n in sel)

for e,z in picked.items():
    print(f"\n■ [{e}] {z.split('/')[-2]}/{z.split('/')[-1]}  (zip {os.path.getsize(z)/1e6:.0f}MB)")
    for scen in ["A","B","C"]:
        t=time.time()
        cnt,sz=extract(z, scen, os.path.join(OUT, f"{scen}_{'mesh_only' if scen=='A' else 'with_textures' if scen=='B' else 'same_folder'}"))
        print(f"  {scen}: 파일 {cnt:4d}개  {sz/1e6:8.1f}MB  ({time.time()-t:.1f}초)")
print("\n결과 위치:", OUT)
