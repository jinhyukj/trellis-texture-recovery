import glob
V = "/workspace/jh/view"
rows = []
for f in sorted(glob.glob(f"{V}/.cmp_*.tsv")):
    for ln in open(f):
        a = ln.rstrip("\n").split("\t")
        if len(a) == 5: rows.append(a)
win = sum(1 for r in rows if int(r[4]) > int(r[3]))
same = sum(1 for r in rows if int(r[4]) == int(r[3]))
lose = sum(1 for r in rows if int(r[4]) < int(r[3]))
h = ["<html><head><meta charset=utf-8><title>Phase A 좌표 A/B</title><style>",
     "body{font-family:sans-serif;background:#222;color:#eee}",
     ".c{display:inline-block;margin:8px;background:#333;padding:8px;border-radius:8px;vertical-align:top}",
     "img{width:300px;height:300px;object-fit:contain;background:#111}",
     ".t{font-size:11px;max-width:620px;word-break:break-all;height:42px;overflow:hidden}",
     ".win{outline:2px solid #3a6} .lose{outline:2px solid #c33}",
     "</style></head><body>",
     f"<h2>Phase A 좌표 효과 — {len(rows)}건 · <span style='color:#3a6'>개선 {win}</span> · 동일 {same} · <span style='color:#c33'>악화 {lose}</span></h2>",
     "<p style='color:#999;font-size:12px'>왼쪽=추측 규칙만 / 오른쪽=Phase A 좌표 사용 · 초록=좌표가 더 많이 배선 · 빨강=좌표가 덜 배선</p>"]
for cid, sp, n, na, nb in rows:
    k = "win" if int(nb) > int(na) else ("lose" if int(nb) < int(na) else "")
    h.append(f"<div class='c {k}'><div class=t>배선 <b>추측 {na}</b> → <b>좌표 {nb}</b> / 텍스처 {n}<br>{sp}</div>"
             f"<img loading=lazy src='cmp/{cid}/a.png'> <img loading=lazy src='cmp/{cid}/b.png'></div>")
h.append("</body></html>")
open(f"{V}/coords.html", "w").write("\n".join(h))
print(f"coords.html: {len(rows)}건 · 개선 {win} · 동일 {same} · 악화 {lose}")
