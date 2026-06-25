"""04 — Compile the status tracker + backlog from the sweep (+ run stats).

Produces (all openable directly — no server):
  - status/migration_status.csv   the live tracker, SOURCE OF TRUTH
  - status/migration_status.xlsx  Excel view (if pandas/openpyxl installed; lock-safe)
  - status/backlog.md             ranked, by plan

New flows start at "Not started". If the tracker already exists, existing status / validated /
signoff values are PRESERVED — re-running discovery never resets your progress.
Run 01 (and 03 for usage columns) first.
"""
import csv, io, json
from _dataprep import ROOT, safe_write_text

COLUMNS = ["plan", "flow", "status", "target", "owner", "last_updated",
           "validated", "signed_off_by", "signed_off_date", "notes"]


def load_existing(path):
    """Key existing rows by (plan, flow) so human-set status/signoff survive a re-run."""
    keep = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                keep[(r.get("plan", ""), r.get("flow", ""))] = r
    return keep


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

    csv_path = ROOT / "status" / "migration_status.csv"
    existing = load_existing(csv_path)

    rows = []
    for fl in flows:
        fid = fl.get("id")
        st = stats.get(str(fid), {})
        plan, flow = pmap.get(fid, "_unplanned"), fl.get("name", f"flow_{fid}")
        prev = existing.get((plan, flow), {})
        rows.append({
            "plan": plan,
            "flow": flow,
            "status": prev.get("status") or "Not started",     # preserve human-set status
            "target": prev.get("target") or "SQL",
            "owner": prev.get("owner") or st.get("last_run_by", ""),
            "last_updated": (st.get("last_run") or "")[:10],
            "validated": prev.get("validated") or "no",
            "signed_off_by": prev.get("signed_off_by", ""),
            "signed_off_date": prev.get("signed_off_date", ""),
            "notes": prev.get("notes") or f"runs:{st.get('runs', 0)} avg_secs:{st.get('avg_duration_secs') or '-'}",
        })
    rows.sort(key=lambda r: (r["plan"], r["flow"]))

    # --- migration_status.csv (source of truth) ---
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(rows)
    safe_write_text(csv_path, buf.getvalue())

    # --- backlog.md ---
    plans_n = len({r["plan"] for r in rows})
    lines = ["# Migration backlog", "", f"{len(rows)} flows across {plans_n} plans. One flow at a time.", ""]
    cur = None
    for r in rows:
        if r["plan"] != cur:
            cur = r["plan"]
            lines.append(f"\n## {cur}")
        box = "x" if r["status"] == "Productionized" else " "
        lines.append(f"- [{box}] {r['flow']} — {r['status']} (owner:{r['owner'] or '-'})")
    safe_write_text(ROOT / "status" / "backlog.md", "\n".join(lines) + "\n")
    print(f"Status tracker: {len(rows)} flows / {plans_n} plans -> status/migration_status.csv + status/backlog.md")

    # --- optional Excel view ---
    try:
        import pandas as pd
        xlsx = ROOT / "status" / "migration_status.xlsx"
        try:
            pd.DataFrame(rows, columns=COLUMNS).to_excel(xlsx, index=False, sheet_name="Migration Status")
            print(f"Excel: {xlsx}")
        except PermissionError:  # file open in Excel / OneDrive lock (WinError 32)
            alt = xlsx.with_name("migration_status_latest.xlsx")
            pd.DataFrame(rows, columns=COLUMNS).to_excel(alt, index=False, sheet_name="Migration Status")
            print(f"Excel locked; wrote {alt}")
    except ImportError:
        print("(pandas/openpyxl not installed — skipped .xlsx; the .csv is the source of truth)")


if __name__ == "__main__":
    main()
