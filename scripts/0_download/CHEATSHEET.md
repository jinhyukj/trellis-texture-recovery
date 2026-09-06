# TRELLIS-500K 새 서버 실행 플랜 (2026-08-24 확정)
# 원칙: raw 보존(삭제 금지) · 다운로드↔렌더링 직렬 · 렌더링=재영님 스크립트(우리 범위 밖)
# 디스크 요구: raw 전체 ≈2.8T + 렌더 출력 → 4T+ 권장
# 매 창: source $BASE/env.sh
D=$TRELLIS_BASE/datasets; L=$TRELLIS_BASE/logs

## 0. 회선 확인 (1분)
curl -so /dev/null -w "%{speed_download} B/s\n" https://huggingface.co/datasets/JeffreyXiang/TRELLIS-500K/resolve/main/ObjaverseXL_github.csv

## Phase 1 — HSSD + ABO 전량 (~0.3T)
# [창 abo]
bash $TRELLIS_BASE/abo_fetch.sh 8 2>&1 | tee $L/abo_fetch.log
python data_toolkit/download.py ABO --root $D/ABO 2>&1 | tee $L/abo.log
python data_toolkit/build_metadata.py ABO --root $D/ABO 2>&1 | tee -a $L/abo.log
# [창 hssd] — 선행: hf auth login (사용자)
python data_toolkit/download.py HSSD --root $D/HSSD 2>&1 | tee $L/hssd.log
python data_toolkit/build_metadata.py HSSD --root $D/HSSD 2>&1 | tee -a $L/hssd.log
# (Toys4k eval — 아무 때나 끼워넣기 가능, 32G)
wget -c -O $D/Toys4k/raw/toys4k_blend_files.zip "https://www.dropbox.com/s/8hi76lvl0x5o9si/toys4k_blend_files.zip?dl=1" 2>&1 | tee $L/toys4k_wget.log
python data_toolkit/download.py Toys4k --root $D/Toys4k 2>&1 | tee $L/toys4k.log
python data_toolkit/build_metadata.py Toys4k --root $D/Toys4k 2>&1 | tee -a $L/toys4k.log

## Phase 2 — ObjaverseXL 1TB 청크 (각 청크: 다운로드 → build_metadata → 재영님 렌더 → 다음)
# C1 (≈1.05T): github 전량 + sketchfab rank 0/4
python data_toolkit/download.py ObjaverseXL --root $D/ObjaverseXL_github 2>&1 | tee $L/github.log
python data_toolkit/build_metadata.py ObjaverseXL --root $D/ObjaverseXL_github 2>&1 | tee -a $L/github.log
python data_toolkit/download.py ObjaverseXL --root $D/ObjaverseXL_sketchfab --rank 0 --world_size 4 2>&1 | tee $L/sketchfab_r0.log
python data_toolkit/build_metadata.py ObjaverseXL --root $D/ObjaverseXL_sketchfab 2>&1 | tee -a $L/sketchfab_r0.log
#   → 여기서 멈추고 재영님 렌더링. 끝나면 C2로.
# C2 (≈0.95T): sketchfab rank 1,2 / 4  (순차로 두 rank)
#   python data_toolkit/download.py ObjaverseXL --root $D/ObjaverseXL_sketchfab --rank 1 --world_size 4 ... (r1 끝나면 r2)
#   → build_metadata 1회 → 렌더
# C3 (≈0.47T): sketchfab rank 3/4 → build_metadata → 렌더
# ※ world_size=4 고정 유지 (중간에 바꾸면 분할 경계 어긋남). sketchfab은 파일 단위라 중단·재개 안전.

## ⚠️ 불변 규칙
# - raw/ 는 삭제 금지 (Step 4~7 재현 근거). ABO tar만 추출·기록 완료 후 삭제 허용 (166G)
# - --check_only 금지 (미구현 — 실제 다운로드 시작됨)
# - build_metadata 는 해당 subset의 download 가 모두 끝난 뒤 1회
# - 다운로드와 렌더링 동시 실행 금지 (디스크 쓰기 경합 — cvlab17에서 실증)
# - 중단→재개 = 같은 명령 재실행 (resume 패치: zip 복구·깨진 zip 재clone·ABO 추출 스킵)
