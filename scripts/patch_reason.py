import ast
p = "/workspace/jh/render_pairs.py"
s = open(p).read()

# wire()가 '이미 살아있어서 스킵'을 보고하도록
old = '''def wire(m,img,force=False):
    m.use_nodes=True; nt=m.node_tree
    if not force and has_live_tex(m): return False  # 대상 불확실할 때만 보수적으로 스킵'''
new = '''SKIP_LIVE=[False]
def wire(m,img,force=False):
    m.use_nodes=True; nt=m.node_tree
    if not force and has_live_tex(m):
        SKIP_LIVE[0]=True; return False   # 이미 정상 텍스처 보유 → 유지'''
assert old in s; s = s.replace(old, new, 1)

# alb 루프: 시도 전 플래그 리셋, 결과를 wired/held/failed 로 분류
old2 = '''            img=bpy.data.images.load(tp)
            matname=os.path.splitext(os.path.basename(mrow[4]))[0].lower()
            done=False'''
new2 = '''            img=bpy.data.images.load(tp)
            matname=os.path.splitext(os.path.basename(mrow[4]))[0].lower()
            done=False; SKIP_LIVE[0]=False'''
assert old2 in s; s = s.replace(old2, new2, 1)

old3 = "            if done: wired+=1"
new3 = '''            if done: wired+=1
            elif SKIP_LIVE[0]: held+=1'''
assert old3 in s; s = s.replace(old3, new3, 1)

old4 = "        wired=0"
new4 = "        wired=0; held=0"
assert old4 in s; s = s.replace(old4, new4, 1)

# 카드에 held 포함
s = s.replace("cards.append((cid,bucket,sp,len(albs),wired))",
              "cards.append((cid,bucket,sp,len(albs),wired,held))")
s = s.replace('_cf.write(f"{cid}\\t{bucket}\\t{sp2}\\t{na}\\t{w}\\n")',
              '_cf.write(f"{cid}\\t{bucket}\\t{sp2}\\t{na}\\t{w}\\t{hd}\\n")')
s = s.replace("for cid,bucket,sp2,na,w in cards:", "for cid,bucket,sp2,na,w,hd in cards:")
s = s.replace("for cid,bucket,sp,na,w in cards:", "for cid,bucket,sp,na,w,hd in cards:")
s = s.replace("albedo {w}/{na}", "albedo {w}/{na} · 보유 {hd}")

ast.parse(s)
open(p, "w").write(s)
print("사유 구분 패치 완료")
