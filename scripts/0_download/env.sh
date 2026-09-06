source "/workspace/jh/trellis500k/miniconda3/etc/profile.d/conda.sh"
conda activate "/workspace/jh/trellis500k/envs/trellis500k"
export PYTHONNOUSERSITE=1
export PIP_CACHE_DIR="/workspace/jh/trellis500k/.cache/pip"
export HF_HOME="/workspace/jh/trellis500k/.cache/huggingface"
export TMPDIR="/workspace/jh/trellis500k/.cache/tmp"          # objaverse clone 임시공간 — 반드시 대용량 디스크
export TRELLIS_BASE="/workspace/jh/trellis500k"
mkdir -p "$HF_HOME" "$TMPDIR"
cd "/workspace/jh/trellis500k/TRELLIS.2"
