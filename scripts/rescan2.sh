#!/bin/bash
# 크래시 시 자동 재개 (최대 40회)
for t in $(seq 1 40); do
  ./blender_app/blender -b --factory-startup -noaudio -P slotscan2.py -- 2 12 > slotscan/log_2.txt 2>&1
  grep -q PART_DONE slotscan/log_2.txt && { echo "PART2_COMPLETE (재시도 $t)"; break; }
done
