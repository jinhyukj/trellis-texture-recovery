#!/bin/bash
# github subset 자동 재시도 루프 (진행 지표 = repo zip 수). 사용: bash github_until_done.sh
source /workspace/jh/trellis500k/env.sh
D=$TRELLIS_BASE/datasets/ObjaverseXL_github; L=$TRELLIS_BASE/logs/github.log
RP=$D/raw/github/extracted
stall=0
while true; do
  before=$(find $RP -type f 2>/dev/null | wc -l)
  set -o pipefail
  python data_toolkit/download.py ObjaverseXL --root $D 2>&1 | tee -a $L
  code=$?
  after=$(find $RP -type f 2>/dev/null | wc -l)
  [ $code -eq 0 ] && { echo "=== github 정상 완료 (zip $after) ==="; break; }
  if [ $after -gt $before ]; then stall=0; echo "=== 크래시, 진행 있음(+$((after-before))) → 60초 후 재시작 ==="; sleep 60
  else stall=$((stall+1)); echo "=== ⚠️ 진행 없는 재시작 $stall/3 ==="
    [ $stall -ge 3 ] && { echo "🔴 자동 재시도 중단 — 진단:"; df -h /workspace | tail -1; tail -30 $L | grep -aE "Error|Errno|denied" | tail -5; exit 1; }
    sleep 120
  fi
done
python data_toolkit/build_metadata.py ObjaverseXL --root $D 2>&1 | tee -a $L
