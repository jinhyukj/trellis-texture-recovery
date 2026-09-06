#!/bin/bash
# 정해진 개수만 다운로드: bash download_n.sh <github|sketchfab> <N> [workers=16]
# 미확보(sha256) 중 metadata 순서대로 N개를 --instances로 지정해 받는다. 재시도 루프 + 장부 확정 포함.
set -u
source /workspace/jh/trellis500k/env.sh
SUB=${1:?github|sketchfab}; N=${2:?개수}; W=${3:-16}
case $SUB in
  github)    D=$TRELLIS_BASE/datasets/ObjaverseXL_github;;
  sketchfab) D=$TRELLIS_BASE/datasets/ObjaverseXL_sketchfab;;
  *) echo "subset은 github|sketchfab"; exit 1;;
esac
L=$TRELLIS_BASE/logs/${SUB}_n.log; INST=/tmp/instances_${SUB}_$$.txt

python - "$SUB" "$D" "$N" "$INST" <<'PY'
import os, sys, pandas as pd
sub, D, N, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
md = pd.read_csv(f"{D}/metadata.csv", usecols=["sha256","file_identifier"])
if sub == "github":
    p = md.file_identifier.str.split("/")
    rel = "raw/github/extracted/"+p.str[3]+"/"+p.str[4]+"/"+p.str[7:].str.join("/")
    have = rel.apply(lambda r: os.path.exists(os.path.join(D, r)))
    skip = set()
    for fn in ("missing_fids.txt","modified_fids.txt"):
        fp = os.path.join(D,"raw/github",fn)
        if os.path.exists(fp): skip |= set(l.strip() for l in open(fp) if l.strip())
    todo = md[~have & ~md.file_identifier.isin(skip)]
else:
    uid = md.file_identifier.str.rstrip("/").str.split("/").str[-1]
    glbroot = os.path.join(D, "raw/hf-objaverse-v1/glbs")
    have_uids = {f[:-4] for dp,_,fs in os.walk(glbroot) for f in fs if f.endswith(".glb")}
    todo = md[~uid.isin(have_uids)]
sel = todo.head(N)
open(out,"w").write("\n".join(sel.sha256))
print(f"[download_n] 미확보 {len(todo):,}개 중 {len(sel):,}개 선정 → {out}")
PY

echo "== $SUB $N개 다운로드 시작 (workers=$W) =="
stall=0
while true; do
  before=$(wc -c < /dev/null)  # placeholder
  set -o pipefail
  OXL_PROCESSES=$W python data_toolkit/download.py ObjaverseXL --root $D --instances $INST 2>&1 | tee -a $L
  code=$?
  [ $code -eq 0 ] && break
  stall=$((stall+1)); echo "== 크래시 → 재시작 ($stall) =="; [ $stall -ge 6 ] && { echo "🔴 6회 실패 — 중단"; exit 1; }
  sleep 30
done
python data_toolkit/build_metadata.py ObjaverseXL --root $D 2>&1 | tee -a $L
rm -f $INST
echo "== 완료: 장부 확정까지 끝 =="
