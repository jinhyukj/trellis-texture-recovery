#!/bin/bash
# 읽기 전용 모니터링: bash check.sh <subset>
: "${TRELLIS_BASE:?source env.sh first}"
s=$1; D=$TRELLIS_BASE/datasets/$s; L=$TRELLIS_BASE/logs
echo "=== [$s] $(date "+%m-%d %H:%M") ==="
ps -eo pid,etime,pcpu,args | grep -E "download.py" | grep -v grep | cut -c1-140
[ -d $D/raw ] && echo "raw files: $(find $D/raw -type f 2>/dev/null | wc -l)  size: $(du -sh $D/raw 2>/dev/null | cut -f1)"
[ -f $D/raw/metadata.csv ] && echo "recorded(raw/metadata.csv): $(tail -n +2 $D/raw/metadata.csv | wc -l)"
df -h $TRELLIS_BASE | tail -1
f=$(ls -t $L/*.log 2>/dev/null | head -1); [ -n "$f" ] && { echo "--- $(basename $f) ---"; tail -c 400 "$f" | tr "\r" "\n" | grep -v "^$" | tail -3 | cut -c1-140; }
