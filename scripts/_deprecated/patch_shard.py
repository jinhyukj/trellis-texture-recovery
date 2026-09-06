import ast
p = "/workspace/jh/render_pairs.py"
s = open(p).read()

# ① 샤딩: RP_SHARD / RP_OF 로 표본을 나눠 병렬 렌더
old = "os.makedirs(VIEW,exist_ok=True)"
new = '''SHARD=int(os.environ.get("RP_SHARD","-1")); OFK=int(os.environ.get("RP_OF","0"))
if OFK>0 and SHARD>=0: picks=picks[SHARD::OFK]
os.makedirs(VIEW,exist_ok=True)'''
assert old in s; s = s.replace(old, new, 1)

# ② 카드 정보를 TSV로 남기고, 샤드 모드에서는 html 생성 생략
old2 = 'html=["<html><head>'
new2 = '''TAG=os.environ.get("RP_OUT","index.html").replace(".html","")
with open(os.path.join(VIEW,f".cards_{TAG}_{max(SHARD,0)}.tsv"),"w") as _cf:
    for cid,bucket,sp2,na,w in cards:
        _cf.write(f"{cid}\\t{bucket}\\t{sp2}\\t{na}\\t{w}\\n")
if OFK>0:
    print("SHARD_DONE",SHARD,len(cards)); raise SystemExit
html=["<html><head>'''
assert old2 in s; s = s.replace(old2, new2, 1)

ast.parse(s)
open(p, "w").write(s)
print("샤딩 패치 완료")
