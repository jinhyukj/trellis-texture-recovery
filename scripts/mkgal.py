# 샤드 렌더 결과(.cards_*.tsv)를 모아 갤러리 html 생성
# usage: python3 mkgal.py <tag> [제목]
import sys, glob, os
V = "/workspace/jh/view"
tag = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else tag
cards = []
for f in sorted(glob.glob(f"{V}/.cards_{tag}_*.tsv")):
    for ln in open(f):
        a = ln.rstrip("\n").split("\t")
        if len(a) == 5: cards.append(a)
full = sum(1 for c in cards if c[4] != "0" and c[4] == c[3])
zero = sum(1 for c in cards if c[4] == "0")
h = ["<html><head><meta charset=utf-8><title>%s</title><style>" % title,
     "body{font-family:sans-serif;background:#222;color:#eee}",
     ".c{display:inline-block;margin:8px;background:#333;padding:8px;border-radius:8px;vertical-align:top}",
     "img{width:280px;height:280px;object-fit:contain;background:#111}",
     ".t{font-size:11px;max-width:580px;word-break:break-all;height:44px;overflow:hidden}",
     ".z{outline:2px solid #c33}</style></head><body>",
     f"<h2>{title} — {len(cards)}건 (완전배선 {full} · 미배선 {zero})</h2>",
     "<p style='color:#999;font-size:12px'>왼쪽=before(회수 전) / 오른쪽=after(확정 텍스처 적용) · 빨간 테두리=미배선</p>"]
for cid, bucket, sp, na, w in cards:
    cls = "c z" if w == "0" else "c"
    h.append(f"<div class='{cls}'><div class=t><b>{bucket}</b> · albedo {w}/{na}<br>{sp}</div>"
             f"<img loading=lazy src='{cid}/before.png'> <img loading=lazy src='{cid}/after.png'></div>")
h.append("</body></html>")
open(f"{V}/{tag}.html", "w").write("\n".join(h))
print(f"{tag}.html 생성: {len(cards)}건 (완전배선 {full}, 미배선 {zero})")
