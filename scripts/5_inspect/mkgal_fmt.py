import glob, sys, os
from collections import defaultdict, Counter
SHARD = sys.argv[1] if len(sys.argv) > 1 else "shard2"
V = f"/workspace/jh/view_{SHARD}"
cards = []
for f in sorted(glob.glob(f"{V}/.cards_*.tsv")):
    for ln in open(f):
        a = ln.rstrip("\n").split("\t")
        if len(a) == 7: cards.append(a)
by = defaultdict(list)
for c in cards: by[c[0]].append(c)
CSS = ("body{font-family:sans-serif;background:#222;color:#eee}"
       ".c{display:inline-block;margin:8px;background:#333;padding:8px;border-radius:8px;vertical-align:top}"
       "img{width:330px;height:330px;object-fit:contain;background:#111}"
       ".t{font-size:11px;max-width:680px;word-break:break-all;height:44px;overflow:hidden}"
       ".part{outline:2px solid #ca3} .zero{outline:2px solid #c33} .held{outline:2px solid #38a}"
       "a{color:#7cf} h2{margin-bottom:4px}")
nav = " · ".join(f"<a href='fmt_{e}.html'>{e} ({len(by[e])})</a>" for e in sorted(by))
for ext, cs in by.items():
    full = sum(1 for c in cs if c[4] == c[3] and c[4] != "0")
    held = sum(1 for c in cs if c[5] == "HELD")
    zero = sum(1 for c in cs if c[4] == "0" and c[5] != "HELD")
    h = [f"<html><head><meta charset=utf-8><title>{SHARD} {ext}</title><style>{CSS}</style></head><body>",
         f"<h2>{SHARD} · <b>{ext}</b> 표본 {len(cs)}건 — 완전배선 {full} · 기존보유 {held} · 미배선 {zero}</h2>",
         f"<p style='font-size:12px'>{nav} | <a href='index.html'>전체</a></p>",
         "<p style='color:#999;font-size:12px'>왼쪽=회수 전 / 오른쪽=확정 텍스처 적용</p>"]
    for ext2, cid, mp, n, w, verdict, wb in cs:
        if verdict == "HELD": k = "c held"
        elif w == "0": k = "c zero"
        elif w != n: k = "c part"
        else: k = "c"
        h.append(f"<div class='{k}'><div class=t><b>{verdict}</b> · {wb} · 배선 {w}/{n}<br>{mp}</div>"
                 f"<img loading=lazy src='{cid}/before.png'> <img loading=lazy src='{cid}/after.png'></div>")
    open(f"{V}/fmt_{ext}.html", "w").write("\n".join(h) + "</body></html>")
idx = [f"<html><head><meta charset=utf-8><title>{SHARD} 포맷별 검수</title><style>{CSS}</style></head><body>",
       f"<h2>{SHARD} 포맷별 표본 갤러리</h2><p style='font-size:14px'>{nav}</p><table style='color:#eee'>"]
idx.append("<tr><th>포맷</th><th>표본</th><th>완전배선</th><th>기존보유</th><th>부분</th><th>미배선</th><th>coord</th></tr>")
for ext in sorted(by):
    cs = by[ext]
    full = sum(1 for c in cs if c[4] == c[3] and c[4] != "0")
    held = sum(1 for c in cs if c[5] == "HELD")
    zero = sum(1 for c in cs if c[4] == "0" and c[5] != "HELD")
    part = len(cs) - full - zero - held
    co = sum(1 for c in cs if c[6] == "coord")
    idx.append(f"<tr><td><a href='fmt_{ext}.html'>{ext}</a></td><td>{len(cs)}</td>"
               f"<td>{full}</td><td>{held}</td><td>{part}</td><td>{zero}</td><td>{co}</td></tr>")
idx.append("</table></body></html>")
open(f"{V}/index.html", "w").write("\n".join(idx))
print(f"갤러리 생성: {len(cards)}건")
for ext in sorted(by):
    cs = by[ext]
    f2 = sum(1 for c in cs if c[4]==c[3] and c[4]!="0"); hd = sum(1 for c in cs if c[5]=="HELD")
    z2 = sum(1 for c in cs if c[4]=="0" and c[5]!="HELD")
    print(f"  {ext:6s} {len(cs):3d}건 · 완전배선 {f2:3d} · 기존보유 {hd:3d} · 부분 {len(cs)-f2-hd-z2:3d} · 미배선 {z2:3d}")
