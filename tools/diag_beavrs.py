import json, urllib.request, urllib.error, time
BASE="http://127.0.0.1:5001"
def post(path,payload):
    data=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=240) as r: return r.status,json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e: return e.code,{"_raw":e.read().decode("utf-8","replace")[:400]}
    except Exception as e: return None,{"_err":str(e)}
inp=open(r"D:\MCNP\输入卡生成器源码\gui\public\examples\beavrs_fullcore_mcnp.i",encoding="utf-8").read()
st,p=post("/api/parse-inp",{"inp":inp}); print("parse",st,p.get("status"),p.get("message",""))
deck=p.get("deck",{}); cells=deck.get("cells",[]); print("cells",len(cells))
t0=time.time(); st2,j=post("/api/preview-lattice",{"surfaces":deck.get("surfaces",""),"tr_cards":deck.get("tr_cards",""),"cells":cells}); dt=time.time()-t0
print("preview",st2,"t=%.1fs"%dt)
print("limit",j.get("limit"),"count",j.get("count"),"detailViable",j.get("detailViable"))
print("leafInstances",len(j.get("leafInstances",[])))
print("outer_bound",j.get("outer_bound"))
