#!/bin/bash
# 포맷별 갤러리 — 사용법: ./rungal.sh <shard> [개수/포맷] [시드] [병렬]
S=${1:-shard2}; N=${2:-32}; SEED=${3:-7}; K=${4:-10}
cd /workspace/jh; rm -rf view_$S; mkdir -p view_$S
for i in $(seq 0 $((K-1))); do
( for t in $(seq 1 20); do
    ./blender_app/blender -b --factory-startup -noaudio -P gal_fmt.py -- $S $N $SEED $i $K > view_$S/log_$i.txt 2>&1
    grep -q SHARD_DONE view_$S/log_$i.txt && break
  done ) &
done
wait
python3 /workspace/jh/mkgal_fmt.py $S
