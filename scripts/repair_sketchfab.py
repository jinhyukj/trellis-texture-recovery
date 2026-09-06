# sk_bad.txt의 파일 삭제 + 장부에서 해당 행 제거 → 재다운로드 대상으로 복귀
import os, pandas as pd
B="/workspace/jh/trellis500k/datasets/ObjaverseXL_sketchfab"
bad=[l.split("\t")[1].strip() for l in open("/workspace/jh/sk_bad.txt") if l.strip()]
led=pd.read_csv(f"{B}/raw/metadata.csv")
badrel={os.path.relpath(p,B) for p in bad}
keep=led[~led.local_path.isin(badrel)]
for p in bad:
    try: os.remove(p)
    except FileNotFoundError: pass
keep.to_csv(f"{B}/raw/metadata.csv", index=False)
print(f"제거: 파일 {len(bad)}개, 장부 {len(led)-len(keep)}행 → 재다운로드 대상")
