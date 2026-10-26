import json, sys, urllib.request, concurrent.futures as cf
names = sys.argv[1].split(",")
def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.geturl().rstrip('/') in ("https://www.bamboohr.com",): return None
            return json.loads(r.read())
    except Exception: return None
def probe(n):
    out=[]
    d=get(f"https://boards-api.greenhouse.io/v1/boards/{n}/jobs")
    if d and d.get("jobs"): out.append(("greenhouse",len(d["jobs"])))
    d=get(f"https://api.lever.co/v0/postings/{n}?mode=json")
    if isinstance(d,list) and d: out.append(("lever",len(d)))
    d=get(f"https://api.ashbyhq.com/posting-api/job-board/{n}")
    if d and d.get("jobs"): out.append(("ashby",len(d["jobs"])))
    d=get(f"https://api.smartrecruiters.com/v1/companies/{n}/postings?limit=1")
    if d and d.get("totalFound"): out.append(("smartrecruiters",d["totalFound"]))
    d=get(f"https://apply.workable.com/api/v1/widget/accounts/{n}")
    if d and d.get("jobs"): out.append(("workable",len(d["jobs"])))
    d=get(f"https://{n}.recruitee.com/api/offers/")
    if d and d.get("offers"): out.append(("recruitee",len(d["offers"])))
    d=get(f"https://{n}.breezy.hr/json")
    if isinstance(d,list) and d: out.append(("breezy",len(d)))
    d=get(f"https://ats.rippling.com/api/v2/board/{n}/jobs")
    if d and d.get("items"): out.append(("rippling",len(d["items"])))
    d=get(f"https://{n}.bamboohr.com/careers/list")
    if d and d.get("result"): out.append(("bamboohr",len(d["result"])))
    return n,out
with cf.ThreadPoolExecutor(8) as ex:
    for n,out in ex.map(probe,names):
        if out: print(n,out)
