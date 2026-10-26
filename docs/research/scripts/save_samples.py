"""Fetch two jobs from each source and save them as trimmed JSON samples.

Usage: python3 docs/research/scripts/save_samples.py docs/research/samples
Long HTML/text description fields are cut to 300 characters to keep files small.
"""
import json, sys, urllib.request
from pathlib import Path

OUT = Path(sys.argv[1])
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"}

def get(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def trim(o):
    if isinstance(o, dict):
        return {k: trim(v) for k, v in o.items()}
    if isinstance(o, list):
        return [trim(v) for v in o]
    if isinstance(o, str) and len(o) > 300:
        return o[:300] + "...[trimmed]"
    return o

SOURCES = {
    "greenhouse_faire": ("https://boards-api.greenhouse.io/v1/boards/faire/jobs?content=true", None, lambda d: {**d, "jobs": d["jobs"][:2]}),
    "lever_wattpad": ("https://api.lever.co/v0/postings/wattpad?mode=json", None, lambda d: d[:2]),
    "ashby_wealthsimple": ("https://api.ashbyhq.com/posting-api/job-board/wealthsimple?includeCompensation=true", None, lambda d: {**d, "jobs": d["jobs"][:2]}),
    "smartrecruiters_canva": ("https://api.smartrecruiters.com/v1/companies/canva/postings?limit=2", None, lambda d: d),
    "workable_borrowell": ("https://apply.workable.com/api/v1/widget/accounts/borrowell", None, lambda d: {**d, "jobs": d["jobs"][:2]}),
    "recruitee_bunq": ("https://bunq.recruitee.com/api/offers/", None, lambda d: {"offers": d["offers"][:2]}),
    "breezy_demo": ("https://breezy.breezy.hr/json", None, lambda d: d[:2]),
    "rippling_nesto": ("https://ats.rippling.com/api/v2/board/nesto/jobs", None, lambda d: {**d, "items": d["items"][:2]}),
    "bamboohr_waabi": ("https://waabi.bamboohr.com/careers/list", None, lambda d: d),
    "workday_sunlife_search": ("https://sunlife.wd3.myworkdayjobs.com/wday/cxs/sunlife/Experienced-Jobs/jobs",
                               {"appliedFacets": {}, "limit": 2, "offset": 0, "searchText": "data scientist"}, lambda d: d),
}

for name, (url, body, cut) in SOURCES.items():
    try:
        d = trim(cut(get(url, body)))
        (OUT / f"{name}.json").write_text(json.dumps({"_request": {"url": url, "method": "POST" if body else "GET", "body": body}, "response": d}, indent=2))
        print("saved", name)
    except Exception as e:
        print("FAILED", name, e)

# Workday job detail: the per-job endpoint behind externalPath
try:
    s = get("https://sunlife.wd3.myworkdayjobs.com/wday/cxs/sunlife/Experienced-Jobs/jobs", {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": "data scientist"})
    path = s["jobPostings"][0]["externalPath"]
    url = f"https://sunlife.wd3.myworkdayjobs.com/wday/cxs/sunlife/Experienced-Jobs{path}"
    d = trim(get(url))
    (OUT / "workday_sunlife_detail.json").write_text(json.dumps({"_request": {"url": url, "method": "GET"}, "response": d}, indent=2))
    print("saved workday detail")
except Exception as e:
    print("FAILED workday detail", e)
