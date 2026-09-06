# shard1 Unity 텍스처 회수 — Mapping Logic 설명서

작성: Claude (회수 파이프라인 작성 에이전트) · 2026-09-02

## 1. 이 데이터가 무엇인가

shard1의 **텍스처 없는 mesh 91,598개** (참조 깨짐 32,905 / 참조 없음 32,632 / 무텍스처 설계 22,754 / stl·ply 3,309) 를 대상으로,
mesh 파일 내부 참조가 아니라 **원천 GitHub repo의 Unity 프로젝트 파일(.mat/.meta)** 을 파싱해 텍스처를 회수한 결과물.

- 회수 성공: **26,479 mesh (28.9%)**
- 저장 위치: `unity_recovered/<org__repo>/<repo 내 경로>` (shard1과 평행한 repo 구조, 기존 트리 무변경)
- 텍스처와 함께 근거 파일(.mat, .meta)도 같은 위치에 저장

## 2. 왜 파일명이 mesh 내부 참조와 안 맞는가 (일치 ~10%는 정상)

회수 대상이 애초에 "**mesh 내부 참조가 깨졌거나(원천 repo에도 그 파일이 없음 — raw 404/트리 대조로 검증) 아예 없는**" mesh들임.
- 작성자는 mesh를 만들 때 자기 PC의 텍스처(예: `C:\...\wood.png`)를 참조로 남겼지만 그 파일은 커밋하지 않았고,
- Unity에서는 **다른 이름의 텍스처 파일**을 재질(.mat)로 입힘.
- 따라서 회수된 텍스처 파일명은 mesh 내부 참조명과 원리적으로 무관. 회수분의 절반(12,788)은 참조 문자열이 아예 없는 mesh라 일치 자체가 불가능.
- **연결 근거는 파일명이 아니라 Unity GUID 체인** (아래).

## 3. 연결 체인 (mapping logic)

Unity는 모든 에셋에 GUID를 부여하고 (`<파일>.meta`의 `guid:`), 연결을 GUID로 기록함.

```
[HIGH 판정]
mesh.fbx.meta 의 externalObjects 섹션
  → 이 mesh에 할당된 재질(.mat)의 GUID를 직접 지목
  → .mat(YAML) 안의 텍스처 GUID들
  → repo 전체 .meta 스캔으로 GUID→파일경로 해석
  → 그 텍스처 파일이 커밋 시점 트리에 실재하면 다운로드
= mesh당 실제 쓰는 텍스처만. 평균 3.7장/mesh. 확정 연결.

[MEDIUM 판정] (HIGH 불가 시 폴백)
mesh 폴더(없으면 부모 폴더) 하위의 모든 .mat 수집
  → 각 .mat의 텍스처 GUID → 파일 해석 → 실재하면 다운로드
= "이 mesh가 쓸 가능성이 있는 후보 전부" (상한 수집).
  이웃 에셋의 텍스처가 섞임. 평균 32.7장/mesh, 최대 300장(캡).
```

- 커밋 고정: 모든 조회는 metadata의 커밋 해시 시점 트리 기준 (`ls-tree <commit>`).
- 다운로드는 partial clone + sparse checkout으로 필요한 blob만.

## 4. 장부 파일 3종

| 파일 | 내용 | 행수 |
|---|---|---|
| `shard1_unity_recovery.csv` | mesh별 판정: `result`(HIGH/MEDIUM/CHAIN_EMPTY/NO_MAT/NO_UNITY/실패), n_mats, n_tex_found/downloaded | 91,598 |
| `shard1_unity_recovery_map.csv` | **mesh(sha256) ↔ 회수 텍스처 경로** 연결표. 1행 = mesh 1 : 텍스처 1 | 748,439 |
| `shard1_unity_recovered_files.csv` | 새로 추가된 모든 파일(텍스처+.mat+.meta) 전수 목록 (repo, 경로, 바이트) | 1,534,648 |

⚠️ **map CSV의 의미**: "이 mesh를 위해 수집한 텍스처" — HIGH 행은 확정 연결, **MEDIUM 행은 후보 집합(superset)**.
MEDIUM에서 mesh당 수십 행이 걸리는 것은 버그가 아니라 상한 수집의 결과.

## 5. 권장 사용법

1. `recovery.csv`에서 `result==HIGH` (4,064 mesh) → map CSV 그대로 사용 (확정).
2. `result==MEDIUM` (22,415 mesh) → 두 가지 중 택:
   a. **슬롯 정확 배선**: mesh와 같은 폴더의 `.mat`(YAML)에서 `m_TexEnvs`의 슬롯별(`_MainTex`=albedo, `_BumpMap`=normal 등) `guid:`를 뽑고, 옆 `.meta`의 guid로 파일 경로 해석.
   b. **간이 휴리스틱**: map CSV에서 mesh와 경로가 가장 가까운/이름 유사한 텍스처 우선, `_diff/_albedo/_D` 파일명 관례로 albedo 선별.
3. 슬롯 구분이 필요 없으면(예: albedo 하나만) 파일명 관례 필터로 충분한 경우가 대부분.

## 6. 알려진 한계

- MEDIUM은 이웃 에셋 텍스처 포함 (위 ⚠️). 정밀화하려면 .prefab/.unity 씬 파싱이 필요하나 표본 검증 결과 추가 수확 ~13%뿐이라 미구현.
- 슬롯(albedo/normal) 정보는 map CSV에 없음 — .mat에 있음.
- repo당 이미지 1GB / mesh당 300장 캡. 초과분은 잘림 (장부의 n_tex_found > n_tex_downloaded로 식별 가능).
- 회수 불가 확정: 텍스처를 안 쓰는 단색 재질(CHAIN_EMPTY 12.3K), .mat 부재(NO_MAT 13.7K), Unity 아님(NO_UNITY 37.6K), 죽은 repo 42 mesh.

## 7. 검증 이력

- 기존 shard1/raw 트리 무변경: 실행 전후 파일 수·mtime 대조 (변경 0).
- 매니페스트 = 디스크 실물 전수 일치, 이미지 매직바이트 전수 통과.
- map 기준 배선 렌더 검증 5건 (buggy 차량, 군인 캐릭터, SNOB 캔 등) — 텍스처 정상 적용 확인.

## 8. 확정 바인딩 CSV (2026-09-03 추가)

`shard1_unity_texture_binding.csv` — **mesh → 재질 → 슬롯 → 텍스처 확정 연결표** (88,120행 / 26,479 mesh 전수).
컬럼: sha256, shard_path, mat_path, slot(_MainTex 등), slot_kind(albedo/normal/...), texture_path, binding.

| binding (mesh 기준) | 의미 | 권장 |
|---|---|---|
| HIGH | mesh.meta가 재질 지목 — 확정 | 그대로 사용 |
| MEDIUM_SINGLE | 근처 재질 1개뿐 — 사실상 확정 | 그대로 사용 |
| MEDIUM_NAME | 이름 유사도 매칭 (Milk.fbx↔Milk.mat) | 그대로 사용 |
| MEDIUM_AMBIG | 후보 상위 3개 병기 — 원천에 기록 없음 | 필요시만, 첫 후보 우선 |
| NO_BINDING/ERR | 슬롯 해석 실패 (재질이 단색이거나 .meta 소실) | map CSV로 폴백 |

map CSV(§4)는 후보 superset, 이 CSV는 정제본 — **렌더 배선은 이 파일 기준**을 권장.

## 9. 등급별 실측 정확도 (2026-09-03, 렌더 눈검증 표본 17)

등급별 표본을 binding CSV대로 배선해 렌더 후 육안 판정한 결과 (표본 소수 — 등급당 3~4개, 오차 큼):

| 등급 | 표본 정확도 | 해석 |
|---|---|---|
| HIGH | 4/4 (100%) | 공식 기록 — 신뢰 가능 |
| MEDIUM_SINGLE | 2/3 (~67%) | 오류 사례: 물뿌리개에 이웃(지우개) 텍스처 |
| MEDIUM_NAME | 1/3 (~33%) | 이름 유사도 임계(0.55)가 느슨 — 오매칭 존재 |
| MEDIUM_UNIQUE_TEX | 2/3 (~67%) | 아틀라스 팩은 잘 맞음, 비-팩은 오류 |
| MEDIUM_AMBIG | 1/4 (~25%) | 1순위 후보도 자주 틀림 |

**권장 수정**: 확실성이 필요하면 **HIGH만 사용** (4,063 mesh). MEDIUM 계열은 "후보 텍스처 참고자료"로 취급하고,
채택 시 오배선 리스크(표본상 1/3~3/4)를 감수할 것. 가중 추정으로 전체 26,479 중 실제 올바른 배선은 **약 13K (절반)** 수준.
텍스처 파일 자체는 모두 같은 repo의 실물이므로, 오류는 "파일이 가짜"가 아니라 "어느 mesh 것인지 배정"의 문제.
