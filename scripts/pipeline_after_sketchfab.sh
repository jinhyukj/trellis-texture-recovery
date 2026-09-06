#!/bin/bash
# 전자동 체인: sketchfab 완료 대기 → 장부확정 → 전수검사 → (문제시 수리·재다운 최대 3회) → github 자동 시작
# 진행 상황: /workspace/jh/PIPELINE.txt  (실패 시 마지막 줄 FAILED — 그때만 AI 호출)
source /workspace/jh/trellis500k/env.sh
D=$TRELLIS_BASE/datasets/ObjaverseXL_sketchfab; P=/workspace/jh/PIPELINE.txt
log(){ echo "[$(date "+%m-%d %H:%M")] $1" >> $P; }
echo "== pipeline 시작 $(date) ==" > $P

log "A. 사용자 sketchfab 루프 종료 대기"
while pgrep -f "sketchfab_until_done.sh" >/dev/null; do sleep 300; done
log "A. 루프 종료 감지 → 수렴 확인 실행"
for i in 1 2 3 4 5; do
  python data_toolkit/download.py ObjaverseXL --root $D >> $TRELLIS_BASE/logs/sketchfab_final.log 2>&1 && { log "A. download.py 정상 종료 (수렴)"; break; }
  log "A. 크래시 → 재시도 $i/5"; sleep 60
  [ $i = 5 ] && { log "FAILED: sketchfab 수렴 실패"; exit 1; }
done

for cycle in 1 2 3; do
  log "B$cycle. build_metadata"
  python data_toolkit/build_metadata.py ObjaverseXL --root $D >> $TRELLIS_BASE/logs/sketchfab_final.log 2>&1
  rec=$(tail -n +2 $D/raw/metadata.csv | wc -l); log "B$cycle. 장부 기록 $rec/168,307"
  log "C$cycle. 전수 무결성 검사 (sha256+mesh)"
  if python /workspace/jh/check_full_sketchfab.py >> $P 2>&1; then
    log "C$cycle. ✅ 전수 통과 → github 시작"
    setsid nohup bash $TRELLIS_BASE/github_until_done.sh > $TRELLIS_BASE/logs/github_nohup.log 2>&1 < /dev/null &
    log "D. github_until_done.sh 가동 — pipeline 완료"; exit 0
  fi
  log "C$cycle. ⚠️ 문제 발견 → 수리(삭제+장부정리) 후 재다운로드"
  python /workspace/jh/repair_sketchfab.py >> $P 2>&1
  for i in 1 2 3 4 5; do
    python data_toolkit/download.py ObjaverseXL --root $D >> $TRELLIS_BASE/logs/sketchfab_final.log 2>&1 && break
    sleep 60; [ $i = 5 ] && { log "FAILED: 수리 재다운로드 수렴 실패"; exit 1; }
  done
done
log "FAILED: 3회 수리에도 문제 잔존 — sk_bad.txt 확인 필요"; exit 1
