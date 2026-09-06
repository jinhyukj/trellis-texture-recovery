# 텍스처 감사 v2 (통합) — 참조 단위 계수 + pack 내장 검출을 한 번에
# usage: python audit_v2.py <shard이름>       예: python audit_v2.py shard2
# out:   shards/<shard>_texture_status_v2.csv
import os, re, sys, json, struct, csv, urllib.parse
from multiprocessing import Pool
import pandas as pd

SHARD = sys.argv[1] if len(sys.argv) > 1 else "shard2"
B = "/workspace/jh/trellis500k/datasets/ObjaverseXL_github"
SH = f"{B}/shards/{SHARD}"
OUT = f"{B}/shards/{SHARD}_texture_status_v2.csv"

IMGEXT = ("png","jpg","jpeg","tga","bmp","tif","tiff","dds","exr","hdr","webp","psd")
TEXRE = re.compile(rb"[\w\-. \\/:]{1,200}\.(?:" + "|".join(IMGEXT).encode() + rb")", re.I)
MAGICS = [b"\x89PNG\r\n", b"\xff\xd8\xff", b"DDS |", b"II*\x00", b"MM\x00*"]

_rc = {}
def repo_files(root):
    if root not in _rc:
        have = set()
        for dp, _, fs in os.walk(root):
            for f in fs: have.add(f.lower())
        _rc[root] = have
        if len(_rc) > 64: _rc.pop(next(iter(_rc)))
    return _rc[root]

def embedded(data):
    """파일 내부에 실제 이미지 데이터가 2장 이상 → pack 내장으로 판정"""
    return sum(data.count(m) for m in MAGICS) >= 2

def classify(found, missing, data, ext):
    if found and missing: return "TEX_PARTIAL"
    if found and not missing: return "TEX_RESOLVED"
    if missing and not found:
        if ext in ("fbx", "blend") and embedded(data): return "TEX_EMBEDDED_PACKED"
        return "TEX_MISSING"
    return None

def audit(row):
    sha, rel = row
    p = os.path.join(SH, rel)
    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    dp = os.path.dirname(p)
    try:
        if not os.path.exists(p): return (sha, rel, ext, "GONE_FILE", 0, 0, "")
        if ext in ("stl", "ply"): return (sha, rel, ext, "NO_TEX_BY_FORMAT", 0, 0, "")
        data = open(p, "rb").read()
        found, missing = [], []

        if ext in ("glb", "gltf"):
            if ext == "glb" and data[:4] == b"glTF":
                jl = struct.unpack("<I", data[12:16])[0]; g = json.loads(data[20:20+jl])
            else:
                g = json.loads(data.decode("utf8", "ignore"))
            imgs = g.get("images", [])
            if not imgs: return (sha, rel, ext, "NO_TEX_BY_DESIGN", 0, 0, "")
            uris = [i.get("uri", "") for i in imgs if i.get("uri") and not i["uri"].startswith("data:")]
            if not uris: return (sha, rel, ext, "TEX_EMBEDDED", 0, 0, "")
            for u in uris:
                q = os.path.normpath(os.path.join(dp, urllib.parse.unquote(u.replace("\\", "/"))))
                (found if os.path.exists(q) else missing).append(os.path.basename(u))

        elif ext == "obj":
            txt = data.decode("utf8", "ignore")
            mtls = [m.strip() for m in re.findall(r"(?im)^mtllib\s+(.+)$", txt)]
            if not mtls: return (sha, rel, ext, "NO_TEX_BY_DESIGN", 0, 0, "")
            fs = set(x.lower() for x in os.listdir(dp))
            texs = []
            for m in mtls:
                bn = os.path.basename(m)
                if bn.lower() not in fs: missing.append(bn); continue
                real = [x for x in os.listdir(dp) if x.lower() == bn.lower()][0]
                mt = open(os.path.join(dp, real), "rb").read().decode("utf8", "ignore")
                texs += [t.strip().split()[-1] for t in re.findall(r"(?im)^map_\w+\s+(.+)$", mt)]
            if not texs and not missing: return (sha, rel, ext, "NO_TEX_BY_DESIGN", 0, 0, "")
            for t in texs:
                bn = os.path.basename(t)
                (found if bn.lower() in fs else missing).append(bn)

        elif ext in ("fbx", "blend", "dae"):
            have = repo_files(os.path.join(SH, rel.split("/")[0]))
            refs = sorted(set(os.path.basename(m.replace(b"\\", b"/")).decode("utf8", "ignore")
                              for m in TEXRE.findall(data)))
            if not refs:
                if ext in ("fbx", "blend") and embedded(data):
                    return (sha, rel, ext, "TEX_EMBEDDED_PACKED", 0, 0, "")
                return (sha, rel, ext, "NO_REF_OR_EMBEDDED", 0, 0, "")
            for r2 in refs:
                (found if r2.lower() in have else missing).append(r2)
        else:
            return (sha, rel, ext, "OTHER", 0, 0, "")

        st = classify(found, missing, data, ext)
        return (sha, rel, ext, st, len(found), len(missing), ";".join(missing[:6]))
    except Exception as e:
        return (sha, rel, ext, "ERR", 0, 0, type(e).__name__)

if __name__ == "__main__":
    df = pd.read_csv(f"{SH}.csv")
    rows = list(df.itertuples(index=False, name=None))
    rows.sort(key=lambda r: r[1].split("/")[0])          # repo 단위 정렬 → 캐시 적중
    print(f"{SHARD}: {len(rows):,} mesh 감사 시작", flush=True)
    with Pool(32) as p, open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sha256", "shard_path", "ext", "tex_status", "n_ref_found", "n_ref_missing", "missing_refs"])
        n = 0
        for r in p.imap(audit, rows, chunksize=64):
            w.writerow(r); n += 1
            if n % 20000 == 0: print(f"  {n:,}/{len(rows):,}", flush=True)
    from collections import Counter
    sub = pd.read_csv(OUT)
    c = Counter(sub.tex_status)
    print(f"\n=== {SHARD} 감사 v2 ({len(sub):,}) ===")
    for k, v in c.most_common(): print(f"  {k:22s} {v:7,} ({v/len(sub)*100:5.1f}%)")
    BK = {"TEX_MISSING","NO_REF_OR_EMBEDDED","TEX_PARTIAL","NO_TEX_BY_DESIGN","NO_TEX_BY_FORMAT"}
    tgt = sum(v for k, v in c.items() if k in BK)
    print(f"\n회수 대상 5버킷: {tgt:,}")
    print(f"저장: {OUT}")
