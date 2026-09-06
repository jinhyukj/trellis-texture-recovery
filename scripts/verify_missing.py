# missing_fids 전수 최종 판정: raw.githubusercontent에서 파일 단위로 존재·지문 확인
import os, time, hashlib, urllib.parse, urllib.request, pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
fids=[l.strip() for l in open(f"{B}/raw/github/missing_fids.txt") if l.strip()]
md=pd.read_csv(f"{B}/metadata.csv", usecols=["sha256","file_identifier"]).set_index("file_identifier")
cats={"MALFORMED":[], "GONE":[], "RECOVERABLE":[], "SHA_DIFF":[], "ERROR":[]}
for i,f in enumerate(sorted(set(fids))):
    p=f.split("/")
    if len(p)<8 or p[2]!="github.com" or not p[3] or not p[4]:
        cats["MALFORMED"].append(f); continue
    org,repo,commit=p[3],p[4],p[6]; inner="/".join(p[7:])
    url=f"https://raw.githubusercontent.com/{org}/{repo}/{commit}/{urllib.parse.quote(inner)}"
    try:
        req=urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            data=r.read()
        sha=hashlib.sha256(data).hexdigest()
        if f in md.index and sha==md.loc[f,"sha256"]:
            cats["RECOVERABLE"].append(f)
        else:
            cats["SHA_DIFF"].append(f)
    except urllib.error.HTTPError as e:
        if e.code in (404,451,410): cats["GONE"].append(f)
        else: cats["ERROR"].append(f"{e.code} {f}")
    except Exception as e:
        cats["ERROR"].append(f"{type(e).__name__} {f}")
    time.sleep(0.4)
print(f"검사 대상(고유): {len(set(fids))}")
for k,v in cats.items(): print(f"{k:12s} {len(v)}")
for k in ("RECOVERABLE","SHA_DIFF","ERROR"):
    for x in cats[k][:5]: print("  ", k, x[:110])
open("/workspace/jh/missing_recoverable.txt","w").write("\n".join(cats["RECOVERABLE"]))
