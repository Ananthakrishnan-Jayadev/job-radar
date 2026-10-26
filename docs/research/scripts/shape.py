import json, urllib.request
def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())
def show(name, obj):
    s = json.dumps(obj, default=str)
    print("==", name, s[:900]); print()
gh = get("https://boards-api.greenhouse.io/v1/boards/faire/jobs")["jobs"][0]; gh.pop("content",None); show("greenhouse", gh)
lv = get("https://api.lever.co/v0/postings/wattpad?mode=json")[0]
for k in ["description","descriptionPlain","lists","additional","additionalPlain","descriptionBody","descriptionBodyPlain","opening","openingPlain"]: lv.pop(k,None)
show("lever", lv)
ab = get("https://api.ashbyhq.com/posting-api/job-board/wealthsimple")["jobs"][0]
for k in ["descriptionHtml","descriptionPlain"]: ab.pop(k,None)
show("ashby", ab)
show("smartrecruiters", get("https://api.smartrecruiters.com/v1/companies/hootsuite/postings?limit=1")["content"][0])
w = get("https://apply.workable.com/api/v1/widget/accounts/borrowell"); show("workable", {k:v for k,v in w.items() if k!="description"})
show("recruitee", {k:v for k,v in get("https://bunq.recruitee.com/api/offers/")["offers"][0].items() if k not in ("description","requirements","open_questions","translations")})
show("breezy", get("https://breezy.breezy.hr/json")[0])
show("rippling", get("https://ats.rippling.com/api/v2/board/nesto/jobs"))
show("bamboohr", get("https://waabi.bamboohr.com/careers/list"))
show("workday", get("https://sunlife.wd3.myworkdayjobs.com/wday/cxs/sunlife/Experienced-Jobs/jobs", json.dumps({"appliedFacets":{},"limit":2,"offset":0,"searchText":"data scientist"}).encode()))
