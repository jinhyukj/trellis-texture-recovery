#!/bin/bash
# Vast 서버 종료 대비 백업 번들 생성 — 코드 + 장부(gzip) + 패치 + 문서
set -u
J=/workspace/jh
B=$J/trellis500k/datasets/ObjaverseXL_github
OUT=$J/backup_trellis_tex
rm -rf $OUT; mkdir -p $OUT/{scripts,ledgers,patches,docs}

# ① 스크립트 전부 (토큰류 제외)
cp $J/*.py $J/*.sh $OUT/scripts/ 2>/dev/null
cp $J/trellis500k/env.sh $J/trellis500k/*.sh $OUT/scripts/ 2>/dev/null
rm -f $OUT/scripts/.gh_token $OUT/scripts/*token* 2>/dev/null

# ② 장부 — 핵심만 gzip (v1 폐기분 제외)
cd $B/shards
for f in shard1.csv shard1.shas shard1_texture_status_v2.csv \
         shard1_confirmed_results.csv shard1_confirmed_files.csv shard1_confirmed_map.csv \
         shard1_binding_coords.csv shard1_binding_verification.csv shard1_appearance_ready.csv \
         shard2.csv shard2.shas shard2_texture_status_v2.csv \
         shard2_confirmed_results.csv shard2_confirmed_files.csv shard2_confirmed_map.csv \
         shard2_binding_verification.csv shard2_appearance_ready.csv; do
  [ -f "$f" ] && gzip -c "$f" > $OUT/ledgers/"$f".gz
done
cp UNITY_RECOVERY_README.md $OUT/docs/ 2>/dev/null

# ③ TRELLIS.2 우리 패치 (diff + 커밋 로그)
cd $J/trellis500k/TRELLIS.2
git diff > $OUT/patches/TRELLIS2_uncommitted.diff 2>/dev/null
git log --oneline -20 > $OUT/patches/TRELLIS2_commits.txt 2>/dev/null
git rev-parse HEAD > $OUT/patches/TRELLIS2_HEAD.txt 2>/dev/null
cp data_toolkit/datasets/ObjaverseXL.py $OUT/patches/ 2>/dev/null

# ④ 원천 metadata (재현에 필수, 소형)
for d in ObjaverseXL_github ABO HSSD Toys4k 3D-FUTURE; do
  m=$J/trellis500k/datasets/$d/metadata.csv
  [ -f "$m" ] && gzip -c "$m" > $OUT/ledgers/metadata_$d.csv.gz
done

# ⑤ 요약
{ echo "생성: $(date -u +%Y-%m-%dT%H:%MZ)"
  echo "스크립트: $(ls $OUT/scripts | wc -l)개"
  echo "장부: $(ls $OUT/ledgers | wc -l)개"
  du -sh $OUT
} > $OUT/MANIFEST.txt
cat $OUT/MANIFEST.txt
du -sh $OUT/*
