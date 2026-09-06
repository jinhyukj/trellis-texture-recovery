#!/bin/bash
# Phase B v2 (렌더 포함) — 사용법: ./runb2.sh <shard> [병렬수]
S=${1:-shard2}; K=${2:-12}
cd /workspace/jh; mkdir -p phase_b_$S
for i in $(seq 0 $((K-1))); do
( for t in $(seq 1 40); do
    ./blender_app/blender -b --factory-startup -noaudio -P phase_b_v2.py -- $S $i $K > phase_b_$S/log_$i.txt 2>&1
    grep -q PART_DONE phase_b_$S/log_$i.txt && break
  done ) &
done
wait
python3 /workspace/jh/phase_b_v2_report.py $S
