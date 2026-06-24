"""04 — Compile the catalog and backlog from the sweep (+ run stats).

Merges flows, their plan, and job stats into:
  - docs/catalog.json      (consumed by docs/catalog.html — the dashboard)
  - output/backlog.md      (ranked, by plan)
  - output/data/catalog.xlsx  (optional, if pandas/openpyxl installed; lock-safe fallback name)

All flows start at status "Not started"; /dp:migrate updates a flow's status as it's migrated.
Run 01 (and 03 for usage columns) first.
"""
import json, datetime
from _dataprep import ROOT, safe_write_text, ENV


def main():
    tmp = ROOT / "output" / "temp"
    flows = json.loads((tmp / "flows.json").read_text(encoding="utf-8"))
    plans = json.loads((tmp / "plans.json").read_text(encoding="utf-8")) if (tmp / "plans.json").exists() else []
    stats = json.loads((tmp / "job_stats.json").read_text(encoding="utf-8")) if (tmp / "job_stats.json").exists() else {}

    pmap = {}
    for p in plans:
        for f in (p.get("flows") or []):
            fid = f.get("id") if isinstance(f, dict) else f
            pmap[fid] = p.get("name", "_unplanned")

    rows = []
    for fl in flows:
        fid = fl.get("id")
        st = stats.get(str(fid), {})
        rows.append({
            "plan": pmap.get(fid, "_unplanned"),
            "flow": fl.get("name", f"flow_{fid}"),
            "target": "SQL",            # discovery default; @flow-inventory may refine
            "source": "", "output": "",
            "status": "Not started",
            "owner": st.get("last_run_by", ""),
            "updated": (st.get("last_run") or "")[:10],
            "runs": st.get("runs", 0),
            "runner_emails": st.get("runner_emails", ""),
            "avg_duration_secs": st.get("avg_duration_secs"),
            "bq_url": "", "docs_url": "", "parity_url": "",
        })
    rows.sort(key=lambda r: (r["plan"], r["flow"]))

    catalog = {
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "project": ENV.get("GCP_PROJECT", "your-gcp-project"),
        "flows": rows,
    }
    safe_write_text(ROOT / "docs" / "catalog.json", json.dumps(catalog, indent=2))

    plans_n = len({r["plan"] for r in rows})
    lines = ["# Migration backlog", "", f"{len(rows)} flows across {plans_n} plans. One flow at a time.", ""]
    cur = None
    for r in rows:
        if r["plan"] != cur:
            cur = r["plan"]
            lines.append(f"\n## {cur}")
        lines.append(f"- [ ] {r['flow']} — runs:{r['runs']} last:{r['updated'] or '—'} owner:{r['owner'] or '—'}")
    safe_write_text(ROOT / "output" / "backlog.md", "\n".join(lines) + "\n")
    print(f"Catalog: {len(rows)} flows / {plans_n} plans -> docs/catalog.json + output/backlog.md")

    try:
        import pandas as pd
        xlsx = ROOT / "output" / "data" / "catalog.xlsx"
        xlsx.parent.mkdir(parents=True, exist_ok=True)
        try:
            pd.DataFrame(rows).to_excel(xlsx, index=False, sheet_name="Dataprep Catalog")
            print(f"Excel: {xlsx}")
        except PermissionError:  # file open in Excel / OneDrive lock
            alt = xlsx.with_name("catalog_database_ready.xlsx")
            pd.DataFrame(rows).to_excel(alt, index=False, sheet_name="Dataprep Catalog")
            print(f"Excel locked; wrote {alt}")
    except ImportError:
        print("(pandas/openpyxl not installed — skipped Excel; catalog.json is the source of truth)")


if __name__ == "__main__":
    main()
