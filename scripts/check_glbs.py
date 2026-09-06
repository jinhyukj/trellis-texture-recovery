import os, sys, json, struct, hashlib, csv
from multiprocessing import Pool
B="/workspace/jh/trellis500k/datasets"

def load_targets():
    targets=[]  # (subset, sha256, path)
    # HSSD: ledger 기준 (완료 subset → 누락도 판정)
    import pandas as pd
    led=pd.read_csv(f"{B}/HSSD/raw/metadata.csv")
    for sha,lp in zip(led.sha256, led.local_path):
        targets.append(("HSSD", sha, os.path.join(B,"HSSD",lp)))
    # sketchfab: 디스크에 있는 파일 기준 (진행 중 subset → 내용 검사만)
    md=pd.read_csv(f"{B}/ObjaverseXL_sketchfab/metadata.csv", usecols=["sha256","file_identifier"])
    uid2sha={fid.rstrip("/").split("/")[-1].split("-")[-1]: sha for fid,sha in zip(md.file_identifier, md.sha256)}
    # sketchfab fileIdentifier: https://sketchfab.com/3d-models/<slug-or-uid>; uid = 마지막 하이픈 뒤가 아니라 URL 끝 uid 전체일 수 있음 → 파일명(uid)로 직접 매칭
    uid2sha2={fid.rstrip("/").split("/")[-1]: sha for fid,sha in zip(md.file_identifier, md.sha256)}
    root=f"{B}/ObjaverseXL_sketchfab/raw/hf-objaverse-v1/glbs"
    n_unmatched=0
    for dp,_,fs in os.walk(root):
        for fn in fs:
            if not fn.endswith(".glb"): continue
            uid=fn[:-4]
            sha=uid2sha2.get(uid) or uid2sha.get(uid)
            if sha is None:
                # uid가 URL 끝에 그대로 없는 경우: 매칭 불가 → sha 검사 생략, 구조 검사만
                n_unmatched+=1; sha=""
            targets.append(("sketchfab", sha, os.path.join(dp,fn)))
    return targets, n_unmatched

def check(t):
    subset, sha, path = t
    r={"subset":subset,"path":path,"err":None}
    try:
        if not os.path.exists(path): r["err"]="MISSING"; return r
        data=open(path,"rb").read()
        if sha:
            h=hashlib.sha256(data).hexdigest()
            if h!=sha: r["err"]="SHA_MISMATCH"; return r
        if len(data)<20 or data[:4]!=b"glTF": r["err"]="BAD_MAGIC"; return r
        ver,length=struct.unpack("<II",data[4:12])
        if length!=len(data): r["err"]=f"LEN_MISMATCH({length}!={len(data)})"; return r
        jlen,jtype=struct.unpack("<II",data[12:20])
        if data[16:20]!=b"JSON": r["err"]="NO_JSON_CHUNK"; return r
        g=json.loads(data[20:20+jlen])
        meshes=g.get("meshes",[])
        prims=sum(len(m.get("primitives",[])) for m in meshes)
        has_pos=any("POSITION" in p.get("attributes",{}) for m in meshes for p in m.get("primitives",[]))
        if not meshes or prims==0 or not has_pos: r["err"]="NO_MESH"; return r
    except Exception as e:
        r["err"]=f"PARSE_FAIL:{type(e).__name__}"
    return r

if __name__=="__main__":
    targets,unmatched=load_targets()
    print(f"검사 대상: {len(targets)}개 (sha 매칭불가 {unmatched}개는 구조검사만)", flush=True)
    with Pool(32) as p:
        results=p.map(check, targets, chunksize=64)
    bad=[r for r in results if r["err"]]
    from collections import Counter
    print("=== 결과 ===")
    for sub in ["HSSD","sketchfab"]:
        subr=[r for r in results if r["subset"]==sub]
        subbad=[r for r in subr if r["err"]]
        print(f"{sub}: {len(subr)}개 검사, 문제 {len(subbad)}개  {dict(Counter(r['err'].split('(')[0] for r in subbad))}")
    with open("/workspace/jh/glb_check_bad.txt","w") as f:
        for r in bad: f.write(f"{r['subset']}\t{r['err']}\t{r['path']}\n")
    print("상세: /workspace/jh/glb_check_bad.txt")
    for r in bad[:10]: print(" ", r["subset"], r["err"], os.path.basename(r["path"]))
