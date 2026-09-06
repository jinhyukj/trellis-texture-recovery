#!/bin/bash
# 서버 상주 상태 데몬: 60초마다 /workspace/jh/STATUS.txt 갱신 (외부 폴링 불필요)
B=/workspace/jh/trellis500k; GL=$B/datasets/ObjaverseXL_sketchfab/raw/hf-objaverse-v1/glbs
prev=0
while true; do
  n=$(find $GL -name "*.glb" 2>/dev/null | wc -l)
  z=$(find $B/datasets/ObjaverseXL_github/raw/github/extracted -type f 2>/dev/null | wc -l)
  t=$(find $B/datasets/Toys4k/raw -type f 2>/dev/null | wc -l)
  {
    echo "== TRELLIS-500K 상태  $(date "+%m-%d %H:%M") =="
    echo "sketchfab : $n / 168,307  (분당 +$(( (n-prev) )))"
    echo "github    : $z files (extracted)"
    echo "Toys4k    : $t files"
    echo "디스크    : $(df -h /workspace | awk "NR==2{print \$3\" 사용 / \"\$4\" 여유\"}")"
    echo "프로세스  : download.py $(ps -eo args | grep -c "^python data_toolkit/download.py") / 루프 $(ps -eo args | grep -c "until_done.sh")"
    for f in $B/logs/sketchfab_r1.log $B/logs/github.log; do [ -f $f ] && echo "$(basename $f): $(tail -c 200 $f | tr "\r" "\n" | grep -v "^$" | tail -1 | cut -c1-80)"; done
  } > /workspace/jh/STATUS.txt.tmp; mv /workspace/jh/STATUS.txt.tmp /workspace/jh/STATUS.txt
  prev=$n; sleep 60
done
