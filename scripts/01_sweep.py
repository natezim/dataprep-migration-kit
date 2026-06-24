"""01 — Sweep all flows and plans (READ-ONLY).

Lists every flow and plan with limit=250 + flowsFilter/plansFilter=all, so nothing is
silently truncated and team-shared / ex-employee resources are included. Plans carry the
embedded `latestPlanSnapshotRun` (use that — NOT /v4/planSnapshotRuns — to map runs).

Output: output/temp/flows.json, output/temp/plans.json
"""
import json
from _dataprep import api_list, ROOT, safe_write_text, TOKEN


def main():
    if not TOKEN:
        raise SystemExit("No DATAPREP_API_TOKEN in .env — copy .env.example to .env and fill it in.")
    flows = api_list("v4/flows", extra={"flowsFilter": "all"})
    plans = api_list("v4/plans", extra={"plansFilter": "all"})
    tmp = ROOT / "output" / "temp"
    safe_write_text(tmp / "flows.json", json.dumps(flows, indent=2))
    safe_write_text(tmp / "plans.json", json.dumps(plans, indent=2))
    print(f"Swept {len(flows)} flows and {len(plans)} plans -> {tmp}")


if __name__ == "__main__":
    main()
