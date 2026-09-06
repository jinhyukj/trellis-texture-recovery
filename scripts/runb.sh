#!/bin/bash
# Phase B 전수 검증 — 크래시 자동 재개 포함
# 사용법: ./runb.sh [병렬수]
K=${1:-12}
cd /workspace/jh
mkdir -p phase_b
for i in $(seq 0 $((K-1))); do
(
  for t in $(seq 1 40); do
    ./blender_app/blender -b --factory-startup -noaudio -P phase_b.py -- $i $K > phase_b/log_$i.txt 2>&1
    grep -q PART_DONE phase_b/log_$i.txt && break
  done
) &
done
wait
python3 /workspace/jh/phase_b_report.py
