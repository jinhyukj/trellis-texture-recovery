# 새 서버 셋업 — Step 3~5를 돌리기까지

## 1. 저장소·환경

```bash
# TRELLIS.2 + 우리 패치
git clone https://github.com/microsoft/TRELLIS.2 && cd TRELLIS.2
git checkout f4b2a70                          # PR#116 기준점
git am <이 저장소>/patches/commits/000*.patch  # 우리 커밋 7개
git apply <이 저장소>/patches/commits/9999-uncommitted.diff

# conda 환경 (python 3.10)
conda create -n trellis500k python=3.10 -y && conda activate trellis500k
bash setup.sh                                  # TRELLIS.2 의 설치 스크립트
# 핵심 버전: objaverse 0.1.7 · pandas 2.3.3 · huggingface_hub 1.28.0 · torch 2.13.0
# 전체는 patches/requirements_freeze.txt 참고

# ⚠️ setup.sh 가 objaverse 를 새로 깔아 우리 패치를 덮어쓴다 → 반드시 다시 복사
cp <이 저장소>/patches/objaverse_lib/sketchfab.py \
   $(python -c "import objaverse,os;print(os.path.dirname(objaverse.__file__))")/xl/
```

## 2. 경로·환경변수 (`env.sh`)

```bash
export TRELLIS_BASE=/<원하는 경로>/trellis500k
export PYTHONNOUSERSITE=1     # 필수: 공용 ~/.local 의 낡은 tqdm·psutil 회피
export HF_HOME=$TRELLIS_BASE/.cache/hf
export TMPDIR=$TRELLIS_BASE/tmp
conda activate trellis500k
```

## 3. GitHub 인증 (Step 3 속도 제한 회피용)

익명 clone은 속도 제한에 자주 걸린다. **fine-grained PAT(권한 없음, public repo 읽기만)**을 만들어:

```bash
echo "<토큰>" > $TRELLIS_BASE/../.gh_token && chmod 600 $TRELLIS_BASE/../.gh_token
cp <이 저장소>/scripts/0_download/gh_askpass.sh /workspace/jh/.gh_askpass
chmod +x /workspace/jh/.gh_askpass
# gh_partial.py 가 GIT_ASKPASS 로 이걸 호출 → 토큰이 명령줄·로그에 안 남는다
```
> 경로가 `/workspace/jh` 로 하드코딩돼 있으니 다른 위치면 `gh_askpass.sh` 안의 경로를 수정할 것.
> **작업 끝나면 토큰 revoke** (github.com/settings/tokens)

## 4. 장부 복원

```bash
D=$TRELLIS_BASE/datasets/ObjaverseXL_github
mkdir -p $D/raw/github

# 명세 — 둘 중 하나
zcat <이 저장소>/ledgers/common/github_metadata_min.csv.gz > $D/metadata.csv   # sha256+URL (32MB)
# 또는 캡션까지 필요하면 Step 1 로 HF에서 재생성:
# python data_toolkit/build_metadata.py ObjaverseXL --root $D --source github

# 소실 목록 — 없으면 죽은 repo 17,554개를 계속 재시도한다
zcat <이 저장소>/ledgers/common/missing_fids.txt.gz > $D/raw/github/missing_fids.txt

# shard 정의 (같은 집합을 다시 받으려면)
mkdir -p $D/shards
zcat <이 저장소>/ledgers/shard2/shard2.shas.gz > $D/shards/shard2.shas
```

## 5. 실행

```bash
cp <이 저장소>/scripts/0_download/{gh_partial.py,gh_shard.sh} $TRELLIS_BASE/
source $TRELLIS_BASE/env.sh
bash $TRELLIS_BASE/gh_shard.sh shard2 999999 12    # Step 2~5 일괄
```
`.shas`가 이미 있으면 Step 2(선정)를 건너뛰고 기존 정의를 재사용한다 → **같은 집합이 보장된다.**

## 6. 확인

```
[shard2 pass 1] 남은 대상: N        ← Step 3 진행
[extract-mode] recorded 137165      ← Step 4 등록
[shard] …/shard2: mesh 137,165개, repo … 하드링크 완료   ← Step 5
```
