#!/bin/bash
# 사용: bash sketchfab_until_done.sh <rank> [world_size=4]
# 크래시 시 자동 재시작하되, "진행 없는 재시작 3연속"이면 근본 장애로 판단하고 멈춰서 진단 출력
source /workspace/jh/trellis500k/env.sh
RANK=${1:?rank}; W=${2:-4}
D=$TRELLIS_BASE/datasets/ObjaverseXL_sketchfab; L=$TRELLIS_BASE/logs/sketchfab_r${RANK}.log
GL=$D/raw/hf-objaverse-v1/glbs
stall=0
while true; do
  before=$(find $GL -name "*.glb" 2>/dev/null | wc -l)
  set -o pipefail
  python data_toolkit/download.py ObjaverseXL --root $D --rank $RANK --world_size $W 2>&1 | tee -a $L
  code=$?
  after=$(find $GL -name "*.glb" 2>/dev/null | wc -l)
  [ $code -eq 0 ] && { echo "=== rank $RANK 정상 완료 (총 $after) ==="; break; }
  if [ $after -gt $before ]; then
    stall=0; echo "=== 크래시했지만 진행 있음 (+$((after-before))) → 30초 후 재시작 ==="; sleep 30
  else
    stall=$((stall+1)); echo "=== ⚠️ 진행 없는 재시작 $stall/3 ==="
    if [ $stall -ge 3 ]; then
      echo "🔴 근본 장애 의심 — 자동 재시도 중단. 진단:"
      df -h /workspace | tail -1
      echo "--- 마지막 에러 ---"; tail -30 $L | grep -aE "Error|error|Errno|denied|403|401" | tail -5
      echo "--- HF 연결 테스트 ---"; curl -so /dev/null -w "HF http=%{http_code} speed=%{speed_download}B/s\n" -m 20 https://huggingface.co/api/datasets/allenai/objaverse
      exit 1
    fi
    sleep 60
  fi
done
