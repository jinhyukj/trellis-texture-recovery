#!/bin/bash
# shard 단위 github 다운로드: bash gh_shard.sh <shard이름> <개수> [workers=12]
# 예: bash gh_shard.sh shard1 150000
# 동작: 선정 목록 고정(.shas) → 수렴 pass 반복 → 장부 확정 → 하드링크 shard 폴더 생성
set -u
source /workspace/jh/trellis500k/env.sh
NAME=${1:?shard이름}; N=${2:?개수}; W=${3:-12}
D=$TRELLIS_BASE/datasets/ObjaverseXL_github; SH=$D/shards; mkdir -p $SH
LIST=$SH/$NAME.shas; L=$TRELLIS_BASE/logs/gh_$NAME.log
PY=$TRELLIS_BASE/envs/trellis500k/bin/python

# ① shard 정의 (이미 있으면 재사용 = 재실행해도 같은 150K)
if [ ! -f $LIST ]; then
  $PY - "$D" "$N" "$LIST" <<'PYEOF'
import os, sys, pandas as pd
D, N, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
md = pd.read_csv(f"{D}/metadata.csv", usecols=["sha256","file_identifier"])
p = md.file_identifier.str.split("/")
rel = "raw/github/extracted/"+p.str[3]+"/"+p.str[4]+"/"+p.str[7:].str.join("/")
have = rel.apply(lambda r: os.path.exists(os.path.join(D, r)))
skip=set()
for fn in ("missing_fids.txt","modified_fids.txt"):
    fp=os.path.join(D,"raw/github",fn)
    if os.path.exists(fp): skip |= set(l.strip() for l in open(fp) if l.strip())
sel = md[~have & ~md.file_identifier.isin(skip)].head(N)
open(out,"w").write("\n".join(sel.sha256))
print(f"[{os.path.basename(out)}] 신규 정의: {len(sel):,}개")
PYEOF
else
  echo "[$NAME] 기존 정의 재사용: $(wc -l < $LIST)개"
fi

# ② 수렴 pass (진행 없으면 종료, 최대 8회)
prev=-1
for pass in 1 2 3 4 5 6 7 8; do
  left=$($PY - "$D" "$LIST" <<'PYEOF'
import os, sys, pandas as pd
D, lst = sys.argv[1], sys.argv[2]
shas=set(l.strip() for l in open(lst) if l.strip())
md=pd.read_csv(f"{D}/metadata.csv", usecols=["sha256","file_identifier"])
md=md[md.sha256.isin(shas)]
p=md.file_identifier.str.split("/")
rel="raw/github/extracted/"+p.str[3]+"/"+p.str[4]+"/"+p.str[7:].str.join("/")
have=rel.apply(lambda r: os.path.exists(os.path.join(D,r)))
skip=set()
for fn in ("missing_fids.txt","modified_fids.txt"):
    fp=os.path.join(D,"raw/github",fn)
    if os.path.exists(fp): skip |= set(l.strip() for l in open(fp) if l.strip())
print((~have & ~md.file_identifier.isin(skip)).sum())
PYEOF
)
  echo "== [$NAME pass $pass] 남은 대상: $left =="
  [ "$left" -eq 0 ] && break
  [ "$left" = "$prev" ] && { echo "진행 없음 — 수렴 종료 (남은 $left = 재시도 불가분)"; break; }
  prev=$left
  GHP_DELAY=${GHP_DELAY:-1} $PY /workspace/jh/trellis500k/gh_partial.py $LIST $W 2>&1 | tee -a $L
done

# ③ 장부 확정
python data_toolkit/download.py ObjaverseXL --root $D --instances $LIST 2>&1 | tail -3 | tee -a $L
python data_toolkit/build_metadata.py ObjaverseXL --root $D 2>&1 | tail -4 | tee -a $L

# ④ 하드링크 shard 폴더 생성 + shard 장부
$PY - "$D" "$LIST" "$SH/$NAME" <<'PYEOF'
import os, sys, pandas as pd
D, lst, out = sys.argv[1], sys.argv[2], sys.argv[3]
shas=set(l.strip() for l in open(lst) if l.strip())
md=pd.read_csv(f"{D}/metadata.csv", usecols=["sha256","file_identifier"])
md=md[md.sha256.isin(shas)]
p=md.file_identifier.str.split("/")
md=md.assign(org=p.str[3], repo=p.str[4], inner=p.str[7:].str.join("/"))
rows=[]; linked=set()
for r in md.itertuples():
    src_repo=os.path.join(D,"raw/github/extracted",r.org,r.repo)
    mesh=os.path.join(src_repo,r.inner)
    if not os.path.exists(mesh): continue
    dst_repo=os.path.join(out, f"{r.org}__{r.repo}")
    if (r.org,r.repo) not in linked:
        for dp,_,fs in os.walk(src_repo):
            for f in fs:
                s_=os.path.join(dp,f); rel=os.path.relpath(s_,src_repo)
                d_=os.path.join(dst_repo,rel)
                os.makedirs(os.path.dirname(d_), exist_ok=True)
                if not os.path.exists(d_): os.link(s_, d_)
        linked.add((r.org,r.repo))
    rows.append({"sha256":r.sha256,"shard_path":os.path.join(f"{r.org}__{r.repo}",r.inner)})
pd.DataFrame(rows).to_csv(out+".csv", index=False)
print(f"[shard] {out}: mesh {len(rows):,}개, repo {len(linked):,}개 하드링크 완료 (+{out}.csv)")
PYEOF
echo "== [$NAME] 전체 완료 =="
