import os, time, hashlib, urllib.parse, urllib.request, pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
rec=[l.strip() for l in open("/workspace/jh/missing_recoverable.txt") if l.strip()]
md=pd.read_csv(f"{B}/metadata.csv", usecols=["sha256","file_identifier"]).set_index("file_identifier")
ok=fail=0
for f in rec:
    p=f.split("/"); org,repo,commit=p[3],p[4],p[6]; inner="/".join(p[7:])
    dst=os.path.join(B,"raw/github/extracted",org,repo,inner)
    if os.path.exists(dst): ok+=1; continue
    url=f"https://raw.githubusercontent.com/{org}/{repo}/{commit}/{urllib.parse.quote(inner)}"
    try:
        data=urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest()==md.loc[f,"sha256"]:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            t=dst+".copytmp"; open(t,"wb").write(data); os.replace(t,dst); ok+=1
        else: fail+=1
    except Exception: fail+=1
    time.sleep(0.3)
print(f"회수 {ok} / 실패 {fail}")
# missing 목록에서 회수분 제거 (진짜 GONE만 남김)
keep=[l.strip() for l in open(f"{B}/raw/github/missing_fids.txt") if l.strip() and l.strip() not in set(rec)]
open(f"{B}/raw/github/missing_fids.txt","w").write("\n".join(sorted(set(keep)))+"\n")
print("missing 잔여:", len(set(keep)))
