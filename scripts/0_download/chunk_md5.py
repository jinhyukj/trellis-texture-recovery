import hashlib, sys
f=sys.argv[1]; CH=1<<30
h=open(f,"rb"); i=0
while True:
    d=h.read(CH)
    if not d: break
    print(i, hashlib.md5(d).hexdigest(), flush=True)
    i+=1
