#!/bin/bash
source /workspace/jh/trellis500k/env.sh
D=$TRELLIS_BASE/datasets/HSSD; L=$TRELLIS_BASE/logs
for i in 1 2 3 4; do
  python data_toolkit/build_metadata.py HSSD --root $D >> $L/hssd.log 2>&1
  n=$(tail -n +2 $D/raw/metadata.csv 2>/dev/null | wc -l)
  echo "[pass $i] recorded=$n" >> $L/hssd.log; echo "[pass $i] recorded=$n"
  [ "$n" -ge 6670 ] && { echo "HSSD_DONE"; exit 0; }
  python data_toolkit/download.py HSSD --root $D >> $L/hssd.log 2>&1
done
python data_toolkit/build_metadata.py HSSD --root $D >> $L/hssd.log 2>&1
echo "HSSD_LOOP_END recorded=$(tail -n +2 $D/raw/metadata.csv | wc -l)"
