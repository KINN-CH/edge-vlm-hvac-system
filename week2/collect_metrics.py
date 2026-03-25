import os, json, requests
from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparser

token = os.environ["GITHUB_TOKEN"]
repo  = os.environ["REPO"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
now = datetime.now(timezone.utc)
week_ago = now - timedelta(days=7)

# 1. Deployment Frequency
commits_url = f"https://api.github.com/repos/{repo}/commits"
params = {"sha": "main", "since": week_ago.isoformat(), "per_page": 100}
r = requests.get(commits_url, headers=headers, params=params)
commits = r.json() if r.status_code == 200 else []
deploy_count = len(commits) if isinstance(commits, list) else 0
df = f"{deploy_count} times/week"

# 2. Lead Time for Changes
prs_url = f"https://api.github.com/repos/{repo}/pulls"
params2 = {"state": "closed", "base": "main", "per_page": 10, "sort": "updated", "direction": "desc"}
r2 = requests.get(prs_url, headers=headers, params=params2)
prs = r2.json() if r2.status_code == 200 else []
lead_times = []
if isinstance(prs, list):
    for pr in prs:
        if pr.get("merged_at"):
            merged_at = dateparser.parse(pr["merged_at"])
            created_at = dateparser.parse(pr["created_at"])
            lead_times.append((merged_at - created_at).total_seconds() / 3600)
lt = f"{round(sum(lead_times)/len(lead_times), 1)} hours" if lead_times else "N/A (no merged PRs)"

# 3. Change Failure Rate
total_merged = len([p for p in (prs if isinstance(prs, list) else []) if p.get("merged_at")])
failed = len([p for p in (prs if isinstance(prs, list) else [])
              if p.get("merged_at") and
              any(k in p.get("title","").lower() for k in ["hotfix","fix","bug","revert"])])
cfr = f"{round(failed/total_merged*100)}%" if total_merged > 0 else "0%"

# 4. MTTR
issues_url = f"https://api.github.com/repos/{repo}/issues"
params3 = {"state": "closed", "labels": "bug", "per_page": 10}
r3 = requests.get(issues_url, headers=headers, params=params3)
issues = r3.json() if r3.status_code == 200 else []
mttr_times = []
if isinstance(issues, list):
    for iss in issues:
        if iss.get("closed_at") and iss.get("created_at"):
            closed = dateparser.parse(iss["closed_at"])
            created = dateparser.parse(iss["created_at"])
            mttr_times.append((closed - created).total_seconds() / 60)
mttr = f"{round(sum(mttr_times)/len(mttr_times))} mins" if mttr_times else "N/A (no closed bug issues)"

# 결과 저장
os.makedirs("week2", exist_ok=True)
metrics = {
    "collected_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    "deployment_frequency": df,
    "lead_time_for_changes": lt,
    "change_failure_rate": cfr,
    "mttr": mttr
}
print(json.dumps(metrics, indent=2, ensure_ascii=False))
with open("week2/dora_metrics.json", "w") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)