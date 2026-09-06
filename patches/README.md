# patches/ — 원본에 우리가 가한 수정 전부

새 서버에서 이 디렉토리만 있으면 파이프라인을 복원할 수 있다.

## commits/ — TRELLIS.2 저장소 패치 (git format-patch)

원본은 `microsoft/TRELLIS.2` 의 **`pr-116` 브랜치, 커밋 `f4b2a70`**.
그 위에 우리가 올린 7개 커밋 + 미커밋 diff.

```bash
git clone https://github.com/microsoft/TRELLIS.2
cd TRELLIS.2 && git checkout f4b2a70
git am ../patches/commits/000*.patch          # 7개 순서대로
git apply ../patches/commits/9999-uncommitted.diff
```

| 패치 | 무엇을 고쳤나 |
|---|---|
| 0001 | **ABO·HSSD·3D-FUTURE·Toys4k 스크립트 이식** — PR#116엔 ObjaverseXL만 있어서 원조 TRELLIS에서 가져옴. 콜백 시그니처 `func(file, metadatum)`로 수정 |
| 0002 | ObjaverseXL 다운로드 프로세스 상한 (`OXL_PROCESSES`, 기본 16) — cpu_count(64)로 동시 clone하면 SATA SSD 랜덤쓰기 포화 |
| 0003 | **재개 지원** — ABO는 이미 추출된 것 건너뛰기, ObjaverseXL은 기존 zip에서 object 회수 (중단 시 `local_path` 영구 유실 문제) |
| 0004 | 중단으로 깨진 repo zip 제거 → 재clone 유도 |
| 0005 | **HSSD 워커 상한** (`HSSD_WORKERS`, 기본 16) — 144 스레드가 HF에 대량 오류 유발 |
| 0006 | **github B′-strict extract 모드** — repo zip 보관을 버리고 "매칭된 mesh + 파싱된 참조"만 추출 (36.4TB → 2.6TB) |
| 0007 | extract 모드에서 refs를 mesh보다 **먼저** 복사 — mesh 존재 = 완전한 세트라는 표식이 되도록 |

## dataset_scripts/ — 패치 적용된 실물 (참고·대조용)

`data_toolkit/datasets/{ABO,HSSD,Toys4k,3D-FUTURE,ObjaverseXL}.py` + `download.py` + `build_metadata.py`.
패치 적용이 잘 됐는지 대조하거나, 급할 때 그대로 덮어써도 된다.

## objaverse_lib/ — ⚠️ 저장소 밖 패치

`pip install objaverse==0.1.7` 로 설치되는 **외부 라이브러리를 직접 수정**한 것.
**`setup.sh`를 새로 돌리면 이 패치가 사라진다** — 반드시 다시 덮어쓸 것.

```bash
cp objaverse_lib/sketchfab.py $(python -c "import objaverse,os;print(os.path.dirname(objaverse.__file__))")/xl/
```

수정 내용 (sketchfab 다운로드용):
- `urllib.request.urlopen(hf_url, timeout=120)` — 원본은 타임아웃이 없어 응답 없는 서버에 영구히 매달림 (4곳)
- 워커별 재시도 3회 — 원본은 워커 하나의 예외가 **풀 전체를 죽여서** 17만 개 중 1개 실패로 처음부터 다시였음

## 그 외 기억할 것

- **`--check_only` 플래그는 선언만 있고 구현이 없다** → 쓰면 진짜 다운로드가 시작됨. 사용 금지
- 공용 `~/.local`의 낡은 tqdm·psutil 때문에 pip가 설치를 건너뜀 → **`PYTHONNOUSERSITE=1` 필수** (env.sh에 포함)
- `raw/metadata.csv`·`raw/merged_records/` 는 **재개의 유일한 상태 파일** — 절대 삭제 금지
