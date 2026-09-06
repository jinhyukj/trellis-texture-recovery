# 인벤토리 — 코드와 장부가 각각 무엇을 하는가

파이프라인 순서대로. **★ = 현재 표준(다음에 쓸 것)**, 나머지는 이력·보조.

---

## 0_download — 데이터셋 수급

TRELLIS.2 `data_toolkit`을 패치해서 6개 subset을 받는 단계.

| 파일 | 하는 일 |
|---|---|
| `env.sh` | 진입점. conda activate + `PYTHONNOUSERSITE=1` + HF_HOME·TMPDIR·TRELLIS_BASE 지정 |
| `CHEATSHEET.md` | subset별 실행 커맨드 모음 |
| ★ `gh_partial.py` | **github mesh 다운로더 본체.** repo 통째 clone(5GB) 대신 **partial clone + sparse-checkout**으로 필요한 mesh와 그 참조 파일만 받음(15배 빠름). 소실 판정 3중(git error → HEAD 404 → raw 파일 확인) |
| ★ `gh_shard.sh` | shard 단위 래퍼. 선정 목록 고정(`.shas`) → 수렴 pass 반복 → 장부 확정 → **하드링크로 shard 폴더 생성** |
| `download_n.sh` | object 개수 지정 다운로드 |
| `github_until_done.sh` / `hssd_until_done.sh` / `sketchfab_until_done.sh` | 진전 없을 때까지 재시도하는 스마트 루프 |
| `pipeline_after_sketchfab.sh` | sketchfab 완료 후 수렴→검사→수리→github 자동 시작 |
| `abo_fetch.sh` | ABO tar를 Range 8분할 병렬 curl (S3 단일 연결이 10~40KB/s로 퇴화해서) |
| `statusd.sh` | 60초마다 STATUS.txt 갱신 (서버측 자동화, 토큰 절약용) |
| `ObjaverseXL_new.py` | 패치된 toolkit 데이터셋 모듈 (extract 모드) |
| **검증·수리** | `check_glbs.py`(4겹: 존재·sha256·GLB구조·mesh POSITION) · `check_abo.py` · `check_full_sketchfab.py` · `check_github_now.py` · `verify_missing.py`(raw 404 판정) · `recover105.py`(비ASCII 경로 회수) · `backfill_uris.py`(URL 인코딩 URI 회수) · `chunk_md5.py`(1GiB 블록 md5로 손상 구간 탐지) · `fill_holes.sh` · `repair_sketchfab.py` |

---

## 1_audit — 텍스처 감사

mesh를 열어 참조를 추출하고 실제 파일 존재를 대조해 버킷 분류.

| 파일 | 하는 일 |
|---|---|
| ★ `audit_v2.py` | **통합 감사기.** 참조를 **하나씩 세서** 부분 결손(`TEX_PARTIAL`) 분리 + 파일 내부 이미지 매직바이트로 pack 내장(`TEX_EMBEDDED_PACKED`) 검출. 아래 3개를 한 패스로 대체 |
| `texture_audit_full.py` | (구) 전수 감사 v1 — "참조 하나라도 있으면 RESOLVED"라 부분 결손을 놓침 |
| `embed_scan.py` | (구) pack 내장 검출 단독 |
| `partial_audit.py` | (구) 참조 단위 재계수 단독 |
| `texture_audit.py` | 표본 감사 (최초 진단용) |

**포맷별 참조 추출 방식**: obj→`mtllib`→`map_*` / gltf·glb→`images` URI / dae→`init_from` / fbx·blend→바이너리 문자열 스캔(이미지 확장자 12종 화이트리스트)

---

## 2_recover — 텍스처 회수

Unity 원천 기록(`.meta`/`.mat`/`.prefab`)을 따라가 텍스처를 받고 배선 좌표를 기록.

| 파일 | 하는 일 |
|---|---|
| ★ `recover_v3.py` | **통합 회수(shard2 표준).** repo 1회 방문에서 텍스처 + 좌표 3종(`slot_index`·`fbx_material_name`·`gameobject_name`)을 동시 수집. clone 실패 자동 재시도·유니코드 디코드·불변식 자동검사 내장 |
| `confirm_recover.py` | (구) shard1 회수. 좌표를 안 담아서 Phase A 재방문이 필요했음 |
| `phase_a.py` | (구) shard1 좌표 보강 — 같은 repo를 두 번째로 방문해 버렸던 이름 필드 수집 |
| `merge_coords.py` | phase_a `.done` → 좌표 CSV 병합 (실행 중 스냅샷 가능) |
| `unity_binding.py` | `.mat` 슬롯 파싱으로 mesh↔슬롯↔텍스처 표 생성 (shard1 중간 산출) |

---

## 3_verify — 배선 검증

"장부대로 붙여봤을 때 실제로 붙는가"를 기계적으로 판정.

| 파일 | 하는 일 |
|---|---|
| ★ `phase_b_v2.py` + `runb2.sh` + `phase_b_v2_report.py` | **검증 표준(shard2).** 임포트 → before 재질 계수 → 규칙대로 배선 → after 계수 → **256px before/after 렌더 픽셀 델타**까지. 판정: `APPLIED`/`HELD`/`NO_VISUAL_EFFECT`/`NO_TEXTURE`/`REGRESSION` |
| `phase_b.py` + `runb.sh` + `phase_b_report.py` | (구) shard1 검증 — 렌더 없이 재질 그래프만 |
| `slotscan.py` / `slotscan2.py` | 장부의 슬롯 번호가 실제 임포트 결과와 맞는지 전수 조사 (`slotscan2`는 Blender 크래시 재개판) |
| `rescan2.sh` | 크래시 시 자동 재개 래퍼 |
| **분석** | `audit_usable.py`(통과분 품질 내역) · `funnel.py`(회수 깔때기) · `difficulty.py`(좌표 필요도) · `slotcheck.py`(표본 슬롯 검사) |

> `REGRESSION = 0` 확인이 이 단계의 핵심 — "있던 텍스처를 우리가 없앴는가"를 증명한다.

---

## 4_output — 최종 매핑표

| 파일 | 하는 일 |
|---|---|
| ★ `make_ready2.py` | 검증 통과(`APPLIED`+`HELD`)만 추려 **재영님이 조인 없이 읽는 최종 표** 생성 |
| `make_ready.py` | (구) shard1용 — 좌표 CSV를 별도 조인해야 했던 버전 |

---

## 5_inspect — 검수·조사 (판단 근거를 만든 도구들)

| 파일 | 하는 일 |
|---|---|
| ★ `gal_fmt.py` + `mkgal_fmt.py` + `rungal.sh` | **포맷별 검수 갤러리.** fbx/obj/blend/dae 32개씩 before/after 렌더 → HTML. 테두리 색으로 완전배선/기존보유/부분/미배선 구분 |
| `render_pairs.py` + `mkgal.py`·`mkgal2.py` + `gal100.sh` | 무작위·버킷별·그룹별 갤러리 (shard1 검수에 사용) |
| `coordcompare.py` + `mkcmp.py` | **좌표 A/B 비교** — "추측 규칙만" vs "Phase A 좌표 사용" 렌더 대조 |
| `preview_extract.py`·`preview_b2.py`·`simulate_extract.py` | 다운로드 방식(A/B/B′) 비교 검증 (초기 설계 결정 근거) |
| **조사** | `texmiss_source_audit.py`(원천에도 없는지 대조) · `nearby_tex_audit.py`(근처 이미지 존재율) · `unity_chain_probe.py`(Unity 체인 성립률) · `probe2.py`(prefab/타엔진 정찰) · `prefab_probe.py` · `prefab_recover30.py`(표본 회수) · `namecheck.py`(이름 좌표 일치율 실측) |

---

## _deprecated

`unity_recover.py`(v1 superset 회수 — 배선 신뢰도 낮아 폐기) + 서버에서 코드 고칠 때 쓴 일회성 `patch_*.py`.

---

# 장부 (ledgers/)

전부 gzip. `<shard>` = shard1 | shard2.

## 선정·수급
| 파일 | 내용 |
|---|---|
| `<shard>.csv` | **sha256 ↔ shard 내 mesh 경로.** 이 shard가 무엇인지 정의 |
| `<shard>.shas` | 선정된 sha256 목록 (재실행해도 같은 집합 보장) |
| `common/metadata_*.csv` | subset별 원천 metadata (github 것은 용량 때문에 제외 — HF에서 재생성) |

## 감사
| 파일 | 내용 |
|---|---|
| `<shard>_texture_status_v2.csv` | **mesh별 텍스처 상태.** `tex_status`(RESOLVED/MISSING/PARTIAL/PACKED/BY_DESIGN…) + 참조 found/missing 개수 + 빠진 파일명 |

## 회수
| 파일 | 내용 |
|---|---|
| `<shard>_confirmed_results.csv` | mesh별 회수 판정 (`*_CONFIRMED`/`*_COLORS_ONLY`/`NO_RECORD`/`NO_UNITY`…) |
| `<shard>_confirmed_files.csv` | **새로 추가된 파일 전수 목록** (repo·경로·크기) — 재영님 요구사항 |
| `<shard>_confirmed_map.csv` | **mesh → 좌표 → 재질 → 텍스처.** shard2는 좌표가 여기 포함, shard1은 아래 coords와 조인 필요 |
| `shard1_binding_coords.csv` | (shard1 전용) Phase A로 뒤늦게 수집한 이름 좌표 |

## 검증·최종
| 파일 | 내용 |
|---|---|
| `<shard>_binding_verification.csv` | mesh별 판정 + before/after 재질 수 + 좌표/폴백 배선 수 + 렌더 델타 |
| `<shard>_appearance_ready.csv` | ⭐ **최종 납품물.** 검증 통과분만, 좌표 3종 + 슬롯 종류 + 알파 + 신뢰 경로 포함 |

---

# 데이터 실물 (백업 제외 — 서버에만 있음)

| 위치 | 크기 | 복구 방법 |
|---|---|---|
| `shards/shard2/` | mesh 137,165 | `gh_shard.sh`로 재다운로드 (`.shas`가 있어 동일 집합 보장) |
| `unity_confirmed/` | 106G | `shard1_confirmed_files.csv`의 목록으로 텍스처만 재수집 |
| `unity_confirmed_shard2/` | 98G | `shard2_confirmed_files.csv` 동일 |
| cvlab17 `/mnt/sde/jinhyuk` | Toys4k 44G · HSSD 22G | **유일본** (Vast엔 metadata만) |

---

# 부록 — Step 1·2 재현에 필요한 것 (전부 이 저장소에 있음)

| 필요한 것 | 어디에 | 비고 |
|---|---|---|
| `env.sh` | `scripts/0_download/` | 진입점 (conda·경로·PYTHONNOUSERSITE) |
| `build_metadata.py`·`ObjaverseXL.py` | `patches/dataset_scripts/` | 또는 `patches/commits/`로 원본에 적용 |
| `gh_shard.sh` | `scripts/0_download/` | 선정·수렴·장부·하드링크 |
| **명세** `github_metadata_min.csv.gz` | `ledgers/common/` | **sha256 + file_identifier**(URL). 재다운로드의 필수 입력. captions·점수는 용량 때문에 제외 — 필요하면 Step 1로 HF에서 재취득 |
| **소실 목록** `missing_fids.txt.gz` | `ledgers/common/` | 17,554개. 없으면 **죽은 repo를 계속 재시도**하게 됨 |
| **다운로드 기록** `github_raw_metadata.csv.gz` | `ledgers/common/` | 294,289행 (`sha256, local_path`). 무엇을 실제로 받았는지의 기록 = 재개의 근거 |
| shard 정의 `shard*.shas.gz` | `ledgers/shard1|2/` | 그 shard가 정확히 어느 집합인지 |
| conda 환경 | ❌ 없음 | `setup.sh`로 재생성 후 **objaverse 패치 다시 덮어쓸 것** |

> ⚠️ `metadata.csv` 원본(captions 포함, 94MB)은 저장소에서 제외했다.
> Step 1 (`build_metadata.py ObjaverseXL --source github`) 한 줄로 HF에서 다시 만들 수 있다.
> 다만 **URL이 없으면 아무것도 못 받으므로** 최소본(sha256+URL)은 위에 백업해뒀다.
