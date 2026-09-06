#!/bin/bash
U=https://amazon-berkeley-objects.s3.amazonaws.com/archives/abo-3dmodels.tar
F=/workspace/jh/trellis500k/datasets/ABO/raw/abo-3dmodels.tar
while read s e; do
  ( curl -s -L -r $s-$((e-1)) "$U" | dd of=$F bs=4M oflag=seek_bytes conv=notrunc seek=$s 2>/dev/null && echo "hole $s OK" || echo "hole $s FAIL" ) &
done < /workspace/jh/holes_s3.txt
wait; echo FILL_END
