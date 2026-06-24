"""03 — Compile per-flow run statistics (READ-ONLY).

Bulk-paginates /v4/jobGroups with embed=creator and aggregates IN MEMORY — the server 500s on
nested-field filters, so we never filter job history by flow server-side. Per flow we compute:
run count, average duration (updatedAt - createdAt), unique runner emails, and last run + by-whom.

Output: output/temp/job_stats.json  (keyed by flow id as a string)
"""
import json, datetime
from collections import defaultdict
from _dataprep import api_list, ROOT, safe_write_text


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:
        return None


def flow_id_of(jg):
    """Best-effort: jobGroups embed the wrangledDataset -> flow. Verify the shape on your version."""
    return (((jg.get("wrangledDataset") or {}).get("flow") or {}).get("id"))


def main():
    jobs = api_list("v4/jobGroups", extra={"embed": "creator"}, page_size=100)
    agg = defaultdict(lambda: {"runs": 0, "durs": [], "emails": set(), "last": None, "by": None})

    for jg in jobs:
        fid = flow_id_of(jg)
        if fid is None:
            continue
        s = agg[fid]
        s["runs"] += 1
        email = (jg.get("creator") or {}).get("email")
        if email and email not in ("Unknown", "N/A"):
            s["emails"].add(email)
        c, u = parse_dt(jg.get("createdAt")), parse_dt(jg.get("updatedAt"))
        if c and u:
            s["durs"].append((u - c).total_seconds())
        if c and (s["last"] is None or c.isoformat() > s["last"]):
            s["last"] = c.isoformat()
            s["by"] = (jg.get("creator") or {}).get("name", "Unknown")

    out = {
        str(fid): {
            "runs": s["runs"],
            "avg_duration_secs": round(sum(s["durs"]) / len(s["durs"]), 1) if s["durs"] else None,
            "runner_emails": ", ".join(sorted(s["emails"])) if s["emails"] else "None",
            "last_run": s["last"],
            "last_run_by": s["by"],
        }
        for fid, s in agg.items()
    }
    safe_write_text(ROOT / "output" / "temp" / "job_stats.json", json.dumps(out, indent=2))
    print(f"Compiled stats for {len(out)} flows from {len(jobs)} job runs")


if __name__ == "__main__":
    main()
