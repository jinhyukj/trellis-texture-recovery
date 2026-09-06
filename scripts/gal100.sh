#!/bin/bash
# 사용법: ./gal100.sh <READY|PHASEA> <개수> <시드> [병렬수]
G=$1; N=${2:-100}; S=${3:-7}; K=${4:-10}
TAG=$(echo $G | tr "A-Z" "a-z")100
rm -f /workspace/jh/view/.cards_${TAG}_*.tsv
for i in $(seq 0 $((K-1))); do
  (RP_GROUP=$G RP_OUT=$TAG.html RP_SHARD=$i RP_OF=$K \
   /workspace/jh/blender_app/blender -b --factory-startup -noaudio \
   -P /workspace/jh/render_pairs.py -- $N $S > /workspace/jh/view/.log_${TAG}_$i 2>&1 &)
done
while pgrep -f "render_pairs.py" > /dev/null; do sleep 10; done
python3 /workspace/jh/mkgal2.py $TAG "$G 그룹"
