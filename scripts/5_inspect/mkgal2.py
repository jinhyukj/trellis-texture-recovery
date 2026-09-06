# 샤드 렌더 결과 → 갤러리 html (배선/보유/실패 3구분)
import sys, glob
V = "/workspace/jh/view"
tag = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else tag
cards = []
for f in sorted(glob.glob(f"{V}/.cards_{tag}_*.tsv")):
    for ln in open(f):
        a = ln.rstrip("\n").split("\t")
        if len(a) == 6: cards.append(a)
def cls(c):
    na, w, hd = int(c[3]), int(c[4]), int(c[5])
    if w == na: return "ok", "완전배선"
    if w + hd == na: return "held", "기존유지"      # 붙였거나 이미 보유
    if w > 0: return "part", "부분배선"
    if hd > 0: return "held", "기존유지"
    return "fail", "미배선"
from collections import Counter
cnt = Counter(cls(c)[1] for c in cards)
h = ["<html><head><meta charset=utf-8><title>%s</title><style>" % title,
     "body{font-family:sans-serif;background:#222;color:#eee}",
     ".c{display:inline-block;margin:8px;background:#333;padding:8px;border-radius:8px;vertical-align:top}",
     "img{width:280px;height:280px;object-fit:contain;background:#111}",
     ".t{font-size:11px;max-width:580px;word-break:break-all;height:44px;overflow:hidden}",
     ".fail{outline:2px solid #c33} .part{outline:2px solid #ca3} .held{outline:2px solid #38a}",
     "</style></head><body>",
     f"<h2>{title} — {len(cards)}건</h2>",
     "<p style='font-size:13px'>" + " · ".join(f"{k} <b>{v}</b>" for k, v in cnt.most_common()) + "</p>",
     "<p style='color:#999;font-size:12px'>왼쪽=before / 오른쪽=after · "
     "<span style='color:#38a'>파랑=이미 텍스처 보유(정상)</span> · "
     "<span style='color:#ca3'>노랑=부분배선</span> · "
     "<span style='color:#c33'>빨강=미배선</span></p>"]
for c in cards:
    cid, bucket, sp, na, w, hd = c
    k, lab = cls(c)
    h.append(f"<div class='c {k}'><div class=t><b>{bucket}</b> · {lab} (배선 {w}/{na}, 보유 {hd})<br>{sp}</div>"
             f"<img loading=lazy src='{cid}/before.png'> <img loading=lazy src='{cid}/after.png'></div>")
h.append("</body></html>")
open(f"{V}/{tag}.html", "w").write("\n".join(h))
print(f"{tag}.html: " + " · ".join(f"{k} {v}" for k, v in cnt.most_common()))
