# 서버측 표본 렌더 갤러리 생성 (Blender 3.6 headless)
# usage: /workspace/jh/blender_app/blender -b --factory-startup -noaudio -P render_pairs.py -- <N> [seed]
import bpy, os, sys, math, csv, glob, random, mathutils, re, difflib
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
D=f"{B}/unity_confirmed/.done"
VIEW="/workspace/jh/view"
argv=sys.argv[sys.argv.index("--")+1:]
N=int(argv[0]); SEED=int(argv[1]) if len(argv)>1 else 42
def _n(x): return re.sub(r"[^a-z0-9]","",x.lower())
ALBSET={"maintex","basemap","basecolormap","basecolor","albedo","albedomap","albedotransparency","diffuse","diffusemap","diffusetex","maintexture","color","tex","base","basetex","basetexture","col","diff"}
def is_alb(slot): return _n(slot) in ALBSET
ALB=("_MainTex","_BaseMap","_BaseColorMap")

res=[]
for f in glob.glob(D+"/*.csv"):
    if f.endswith((".files.csv",".map.csv")): continue
    res+=[r for r in csv.reader(open(f)) if len(r)>6 and r[3].endswith("_CONFIRMED")]
GRP=os.environ.get("RP_GROUP","")
if GRP:
    import glob as _g
    ready=set(); phasea=set()
    for _f in _g.glob("/workspace/jh/slotscan/part_*.csv"):
        for _r in csv.reader(open(_f)):
            if not _r: continue
            if _r[2].startswith("IMPORT"): continue
            (ready if (_r[1]=="HAS_SLOT" and _r[2]=="FIT") else phasea).add(_r[0])
    sel = ready if GRP.upper().startswith("READY") else phasea
    res=[r for r in res if r[0] in sel]
    print("GROUP", GRP, "후보", len(res), flush=True)
BK=os.environ.get("RP_BUCKET","")
if BK:
    res=[r for r in res if BK.upper() in r[1].upper()]
FILT=os.environ.get("RP_FILTER","")
if FILT:
    pats=[x for x in FILT.split(";") if x]
    picks=[r for r in res if any(p.lower() in r[2].lower() for p in pats)][:N]
else:
    random.seed(SEED); random.shuffle(res)
    picks=[]; per={}
    for r in res:
        if per.get(r[1],0)>=(N if (BK or GRP) else max(2,N//4)): continue
        picks.append(r); per[r[1]]=per.get(r[1],0)+1
        if len(picks)>=N: break
SHARD=int(os.environ.get("RP_SHARD","-1")); OFK=int(os.environ.get("RP_OF","0"))
if OFK>0 and SHARD>=0: picks=picks[SHARD::OFK]
os.makedirs(VIEW,exist_ok=True)

def setup_and_render(png):
    sc=bpy.context.scene
    cam=bpy.data.objects.new("Cam",bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera=cam
    mn=mathutils.Vector((1e9,)*3); mx=mathutils.Vector((-1e9,)*3)
    for o in bpy.data.objects:
        if o.type=="MESH":
            for v in o.bound_box:
                w=o.matrix_world@mathutils.Vector(v)
                mn=mathutils.Vector(map(min,mn,w)); mx=mathutils.Vector(map(max,mx,w))
    c=(mn+mx)/2; r=max((mx-mn).length,0.1)
    cam.location=c+mathutils.Vector((r*0.8,-r*0.8,r*0.45))
    cam.rotation_euler=(cam.location-c).to_track_quat("Z","Y").to_euler()
    cam.data.clip_end=max(1000,r*10)
    sun=bpy.data.objects.new("Sun",bpy.data.lights.new("s","SUN")); sc.collection.objects.link(sun)
    sun.rotation_euler=(math.radians(50),0,math.radians(40)); sun.data.energy=4
    try:
        sc.render.engine="BLENDER_EEVEE"
    except Exception:
        sc.render.engine="BLENDER_WORKBENCH"
    sc.render.resolution_x=480; sc.render.resolution_y=480
    sc.render.filepath=png
    bpy.ops.render.render(write_still=True)

def imp(meshp):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lo=meshp.lower()
    if lo.endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=meshp)
    elif lo.endswith(".obj"):
        try: bpy.ops.wm.obj_import(filepath=meshp)
        except AttributeError: bpy.ops.import_scene.obj(filepath=meshp)
    elif lo.endswith(".dae"): bpy.ops.wm.collada_import(filepath=meshp)
    elif lo.endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=meshp)
    else: raise RuntimeError("fmt")

def has_live_tex(m):
    if not m.use_nodes or not m.node_tree: return False
    import os as _os
    for n in m.node_tree.nodes:
        if n.type=="TEX_IMAGE" and n.image:
            if getattr(n.image,"source","") == "GENERATED": continue   # 생성 placeholder
            _nm=re.sub(r"\.\d+$","",n.image.name).lower()
            if _nm.split(".")[0] in ("checker","grid","default","notexture","untitled","none","placeholder"):
                continue                                               # 이름상 placeholder
            fp=bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
            if n.image.packed_file or (fp and _os.path.exists(fp)): return True
    return False

def _stem(x):
    x=re.sub(r"\.\d+$","",x)          # Blender 중복 접미사 .001 제거
    return os.path.splitext(x)[0].lower()

def repoint(m, img, texfile):
    """mesh가 이미 참조하던 (깨진) 이미지와 파일명이 같으면 그 노드의 이미지를 교체.
       기존 연결(Base Color 등)이 그대로 살아있어 가장 정확한 복원."""
    if not m.use_nodes or not m.node_tree: return False
    tgt=_stem(texfile); ok=False
    for n in m.node_tree.nodes:
        if n.type=="TEX_IMAGE" and n.image and _stem(n.image.name)==tgt:
            fp=bpy.path.abspath(n.image.filepath) if n.image.filepath else ""
            broken = not n.image.packed_file and not (fp and os.path.exists(fp))
            if broken:
                n.image=img; ok=True
    return ok

SKIP_LIVE=[False]
def wire(m,img,force=False):
    m.use_nodes=True; nt=m.node_tree
    if not force and has_live_tex(m):
        SKIP_LIVE[0]=True; return False   # 이미 정상 텍스처 보유 → 유지
    bsdf=next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"),None)
    if not bsdf: return False
    if bsdf.inputs["Alpha"].default_value==0: bsdf.inputs["Alpha"].default_value=1.0
    m.blend_method="OPAQUE"
    t=nt.nodes.new("ShaderNodeTexImage"); t.image=img
    nt.links.new(t.outputs["Color"],bsdf.inputs["Base Color"]); return True

cards=[]
for r in picks:
    sha,bucket,sp=r[0],r[1],r[2]
    key=sp.split("/")[0]
    meshp=os.path.join(B,"shards/shard1",sp)
    if not os.path.exists(meshp): continue
    name=os.path.splitext(os.path.basename(sp))[0].replace(" ","_")
    cid=f"{sha[:10]}_{name}"[:60]
    cdir=os.path.join(VIEW,cid); os.makedirs(cdir,exist_ok=True)
    maps=[m for m in csv.reader(open(f"{D}/{key}.map.csv")) if m[0]==sha]
    try:
        imp(meshp); setup_and_render(os.path.join(cdir,"before.png"))
        imp(meshp)
        albs=[]; _seen=set()
        for m in maps:
            if m[8]!="1" or not is_alb(m[5]): continue
            k=(m[4],m[6])
            if k in _seen: continue
            _seen.add(k); albs.append(m)
        wired=0; held=0
        for mrow in albs:
            tp=os.path.join(B,"unity_confirmed",mrow[2],mrow[6])
            if not os.path.exists(tp): continue
            img=bpy.data.images.load(tp)
            matname=os.path.splitext(os.path.basename(mrow[4]))[0].lower()
            done=False; SKIP_LIVE[0]=False
            texfile=os.path.basename(mrow[6])
            for m in bpy.data.materials:          # 0순위: 깨진 동명 참조 복원
                if repoint(m,img,texfile): done=True
            for m in bpy.data.materials:
                if m.name.lower().startswith(matname[:12]) or matname.startswith(m.name.lower()[:12]):
                    if wire(m,img): done=True
            if not done and mrow[3] not in ("","None"):
                try: si=int(mrow[3])
                except: si=None
                if si is not None:
                    for o in bpy.data.objects:
                        if o.type=="MESH" and len(o.material_slots)>si and o.material_slots[si].material:
                            if wire(o.material_slots[si].material,img): done=True
            if not done:
                mn=_n(os.path.splitext(os.path.basename(mrow[4]))[0])
                cands=[]
                for o in bpy.data.objects:
                    if o.type!="MESH": continue
                    on=_n(o.name)
                    if len(on)<3: continue
                    r=difflib.SequenceMatcher(None,on,mn).ratio()
                    if on in mn or mn.endswith(on) or r>=0.4: cands.append((r,o))
                if cands:
                    best=max(c[0] for c in cands)
                    for r,o in cands:
                        if r < best-0.05: continue
                        if not o.material_slots:
                            o.data.materials.append(bpy.data.materials.new(o.name+"_conf"))
                        for ms in o.material_slots:
                            if ms.material is None: ms.material=bpy.data.materials.new(o.name+"_conf")
                            if wire(ms.material,img): done=True
            if not done and len(albs)==1:
                # mesh 전체 재질이 1개일 때만 전체 적용 (다중 재질이면 오적용 위험 → 스킵)
                allslots=[ms for o in bpy.data.objects if o.type=="MESH" for ms in o.material_slots]
                if len(set(ms.material for ms in allslots if ms.material))<=1:
                    for o in bpy.data.objects:
                        if o.type!="MESH": continue
                        if not o.material_slots:
                            mm=bpy.data.materials.new("c"); o.data.materials.append(mm)
                        for ms in o.material_slots:
                            if ms.material is None: ms.material=bpy.data.materials.new("c")
                            if wire(ms.material,img): done=True
            if done: wired+=1
            elif SKIP_LIVE[0]: held+=1
        setup_and_render(os.path.join(cdir,"after.png"))
        cards.append((cid,bucket,sp,len(albs),wired,held))
        print("OK",cid,flush=True)
    except Exception as e:
        print("FAIL",cid,type(e).__name__,flush=True)

TAG=os.environ.get("RP_OUT","index.html").replace(".html","")
with open(os.path.join(VIEW,f".cards_{TAG}_{max(SHARD,0)}.tsv"),"w") as _cf:
    for cid,bucket,sp2,na,w,hd in cards:
        _cf.write(f"{cid}\t{bucket}\t{sp2}\t{na}\t{w}\t{hd}\n")
if OFK>0:
    print("SHARD_DONE",SHARD,len(cards)); raise SystemExit
html=["<html><head><meta charset=utf-8><title>확정 회수 검수</title><style>body{font-family:sans-serif;background:#222;color:#eee} .c{display:inline-block;margin:10px;background:#333;padding:10px;border-radius:8px} img{width:340px;height:340px;object-fit:contain;background:#111} .t{font-size:12px;max-width:700px;word-break:break-all}</style></head><body>"]
html.append(f"<h2>확정 회수 표본 {len(cards)}건 (before / after)</h2>")
for cid,bucket,sp,na,w,hd in cards:
    html.append(f"<div class=c><div class=t><b>{bucket}</b> · albedo {w}/{na} · 보유 {hd}<br>{sp}</div><img src='{cid}/before.png'> <img src='{cid}/after.png'></div>")
html.append("</body></html>")
open(os.path.join(VIEW, os.environ.get("RP_OUT") or ("pick.html" if os.environ.get("RP_FILTER") else "index.html")),"w").write("\n".join(html))
print("GALLERY", len(cards))
