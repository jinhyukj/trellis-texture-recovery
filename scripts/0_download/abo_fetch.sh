#!/bin/bash
# ABO abo-3dmodels.tar 병렬 Range 다운로드. 사용: bash abo_fetch.sh [parts=8]  (재실행=이어받기)
set -u
: "${TRELLIS_BASE:?source env.sh first}"
U=https://amazon-berkeley-objects.s3.amazonaws.com/archives/abo-3dmodels.tar
OUT=$TRELLIS_BASE/datasets/ABO/raw/abo-3dmodels.tar
TMP=$TRELLIS_BASE/datasets/ABO/raw/.parts; mkdir -p $TMP
N=${1:-8}
SIZE=$(curl -sIL "$U" | grep -i content-length | tail -1 | tr -dc 0-9)
echo "total=$SIZE bytes parts=$N"
CH=$(( (SIZE + N - 1) / N ))
for i in $(seq 0 $((N-1))); do
  s=$((i*CH)); e=$(( (i+1)*CH - 1 )); [ $e -ge $SIZE ] && e=$((SIZE-1))
  want=$((e-s+1)); f=$TMP/part_$i
  if [ -f $f ] && [ $(stat -c %s $f) -eq $want ]; then echo "part_$i done, skip"; continue; fi
  ( have=0; [ -f $f ] && have=$(stat -c %s $f)
    curl -s -L -r $((s+have))-$e "$U" >> $f
    [ $(stat -c %s $f) -eq $want ] && echo "part_$i OK" || echo "part_$i INCOMPLETE — 재실행하면 이어받음" ) &
done
wait
ok=1; for i in $(seq 0 $((N-1))); do s=$((i*CH)); e=$(( (i+1)*CH - 1 )); [ $e -ge $SIZE ] && e=$((SIZE-1)); [ $(stat -c %s $TMP/part_$i 2>/dev/null || echo 0) -eq $((e-s+1)) ] || ok=0; done
if [ $ok = 1 ]; then
  echo "merging..."; cat $(for i in $(seq 0 $((N-1))); do echo $TMP/part_$i; done) > $OUT
  [ $(stat -c %s $OUT) -eq $SIZE ] && { echo "DONE: $OUT"; rm -rf $TMP; } || echo "MERGE SIZE MISMATCH"
else echo "일부 part 미완 — 재실행"; fi
