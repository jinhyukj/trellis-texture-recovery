# TRELLIS-500K github 텍스처 회수 파이프라인

Objaverse-XL github 소스 mesh의 **깨진/누락 텍스처를 Unity 원천 기록으로 복원**하는 파이프라인과 그 산출 장부.
2026-08~09 Vast 서버에서 수행. 서버 종료(2026-09-07) 대비 백업.

## 왜 필요했나

github 소스 mesh는 텍스처가 심하게 결손돼 있다 (shard1 기준 텍스처 정상 41.6%).
원인은 게임 개발자가 mesh만 커밋하고 텍스처는 로컬/에셋스토어에만 두기 때문 —
**mesh 내부 참조가 작성자 PC의 절대경로라 유령 링크**가 된다.

핵심 발견: **Unity 프로젝트는 연결 정보를 mesh 밖에 따로 기록한다.**

| 파일 | 역할 |
|---|---|
| `<파일>.meta` | 모든 에셋의 GUID (번호표). GUID→경로 전화번호부를 만들려면 repo 전체 스캔 필요 |
| `.mat` | 재질 레시피 — 슬롯별(`_MainTex`=albedo, `_BumpMap`=normal…) 텍스처를 GUID로 지목 |
| `.prefab` / `.unity` | **씬 조립 기록** — "이 mesh의 슬롯[i]에 이 재질". mesh↔재질의 유일한 원천 기록 |

확정 체인: `mesh.fbx.meta`(GUID) → prefab의 `MeshFilter(33)` → 같은 GameObject의 `MeshRenderer(23)`
→ `m_Materials[i]` → `.mat` → 슬롯별 텍스처 GUID → 전화번호부로 경로 해석.
캐릭터는 `SkinnedMeshRenderer(137)` 한 문서에 mesh+재질이 함께 있다.

> `m_Materials` 배열 인덱스 = mesh 내부 submesh 번호. 단, **renderer 단위로 0부터 다시 시작**하므로
> fbx 하나에 오브젝트가 여러 개면 번호가 겹친다 → GameObject 이름이 함께 있어야 구분된다.

## 원칙 — 추측 금지

v1에서 "mesh 폴더 근처의 .mat을 전부 긁는" 근접 휴리스틱을 썼다가 실패했다
(렌더 눈검증 실측 정확도: 근접 25% · 이름유사도 33% · mesh.meta 기록 100%).
v2부터는 **원천 기록(mesh.meta ∪ prefab/씬)이 지목한 것만** 채택하고, 모르면 빈칸으로 남긴다.

## 실적

| | shard1 | shard2 |
|---|---|---|
| mesh 수 | 157,124 | 137,165 |
| 회수 대상(텍스처 문제) | 91,716 | 83,858 |
| 확정 회수 | 11,076 | 9,547 |
| 검증 통과(APPLIED+HELD) | — | 8,648 (90.6%) |
| 좌표 기여도 | 47% (2패스) | **88% (1패스 통합)** |
| REGRESSION(있던 텍스처 손실) | — | **0** |

## 재현 순서

```bash
# 0) 준비 — TRELLIS.2 clone + patches/ 적용, metadata는 HF에서 재생성
#    (metadata_ObjaverseXL_github.csv 는 용량 때문에 제외 — toolkit Step 2로 재생성)

# 1) 텍스처 감사 v2 — 참조 단위 계수 + pack 내장 검출
python audit_v2.py <shard>          # → <shard>_texture_status_v2.csv

# 2) 통합 회수 — 텍스처 + 배선 좌표를 repo 1회 방문에 동시 수집
RV_WORKERS=16 python recover_v3.py <shard>
#   → unity_confirmed_<shard>/ + <shard>_confirmed_{results,files,map}.csv

# 3) 검증 — 재질 그래프 계수 + 렌더 델타
./runb2.sh <shard> 12               # → <shard>_binding_verification.csv

# 4) 최종 매핑표 (APPLIED+HELD만)
python make_ready2.py <shard>       # → <shard>_appearance_ready.csv

# (선택) 포맷별 검수 갤러리
./rungal.sh <shard> 32 7 10         # → view_<shard>/index.html, http.server로 열람
```

## 최종 산출물 사용법

`<shard>_appearance_ready.csv` 한 줄 = **"이 mesh의 이 자리에 이 텍스처"**

```
sha256 | mesh_path | repo | texture_path | tex_slot | mat_path
       | slot_index | fbx_material_name | gameobject_name      ← 좌표 3종
       | mat_alpha | verdict | wired_by | render_diff
```

적용 규칙 (이 순서를 지킬 것):
```
1. slot_index 있으면       → mesh.materials[i]
2. fbx_material_name 있으면 → 재질 이름으로 조회 (비ASCII 원문 그대로 저장돼 있음)
3. gameobject_name 있으면   → 오브젝트 이름으로 조회 (완전일치 → 접두/포함 → 유사도)
                              ※ 인스턴스명에 접미사가 붙음: "Ruin 06" vs "Ruin 06 Dark Grey"
4. 공통: 살아있는 텍스처가 있는 재질은 건드리지 않는다 (fill-only)
         단 placeholder(checker/grid/default…)는 예외로 교체 허용
5. mat_alpha == 0 이면 1로 클램프 (안 하면 렌더에서 물체가 통째로 사라짐)
```

더 보수적으로 쓰려면 `wired_by == "coord"`(원천 기록 확정분) 또는 `render_diff > 0.05`로 필터.

## 🕳️ 지뢰 (전부 실제로 당한 것)

| 함정 | 증상 | 대응 |
|---|---|---|
| **`git ls-tree -l`** | partial clone에서 blob 크기 조회가 **파일마다 서버 왕복** → 무조건 타임아웃 | 크기 조회 절대 금지 (제거하니 repo당 10분 → 10초) |
| 고정 타임아웃 잔존 | git 호출 하나라도 배수 미적용이면 대형 repo 전멸 | 모든 호출을 `run()` 경유 + `*_TMULT` |
| **라벨링 버그 패턴** | "코드가 확정 분기에 도달"=CONFIRMED로 기록 → 텍스처 0장인데 CONFIRMED | **결과물 검사 후 라벨** + 파이프라인 끝에 불변식 자동검사 |
| 유니코드 이름 | Unity YAML이 비ASCII를 `\uXXXX`로 저장 → 중국어/러시아어 재질 매칭 실패 | `dec()` 디코더 필수 |
| `_stem` 순서 | `sky.jpg.001`에서 확장자를 먼저 떼면 `skyjpg` ≠ `sky` | `.NNN`을 **먼저** 제거 후 확장자 (⚠️ 현 코드 미수정) |
| fbx 알파=0 | 원본이 완전 투명으로 수출됨 → 렌더에 아무것도 안 보임 | 알파 1 클램프 |
| UV 부재 | 텍스처 배선해도 단색 (정점 379 vs UV 20) | `NO_VISUAL_EFFECT`로 분류 |
| `cat dir/*.csv` | 파일 3만 개면 argument list too long → **조용히 0 반환** | `find -print0 \| xargs -0` |
| Blender 크래시 | 손상 .blend에서 세그폴트 → 파이썬 try/except로 못 잡음 | 건별 flush + 크래시 지점 마커로 재개 시 스킵 |
| pgrep 자기매칭 | 대기 루프가 자기 명령줄을 잡아 무한 대기 | PID 지정 또는 완료 마커 파일로 판정 |

## 회수 불가로 확정된 것

| 사유 | shard2 규모 | 설명 |
|---|---|---|
| Unity 아님 | 37,973 (45%) | .meta가 없는 repo — 이 방식이 원리적으로 적용 불가 |
| NO_RECORD | 28,015 (33%) | Unity지만 씬에 배치된 적 없음 → 기록 자체가 없음 |
| NO_MESH_META | 2,838 | mesh의 .meta가 미커밋 |

비-Unity 대안(Godot `.tscn` 파서 등)은 표본 8%로 수확 대비 비용이 맞지 않아 보류.

## 폐기된 산출물 (참고)

`unity_recovered/`(v1, superset 방식)와 `shard1_unity_*.csv` 계열은 배선 신뢰도가 낮아 폐기.
v1은 텍스처 파일 자체는 진짜였고 **"누구 것인가"가 틀렸다** — 백업에서 제외했다.
