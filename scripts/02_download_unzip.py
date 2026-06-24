"""02 — Download each flow's package and extract it (READ-ONLY export).

For every swept flow, GET /v4/flows/{id}/package (the same ZIP the UI "Export Flow" produces)
and extract it to flows/<plan>/<flow>/recipe/ with Windows-safe folder names. Run 01 first.

NOTE: this only READS from Dataprep. It never modifies a flow, recipe, or output.
"""
import io, json, zipfile
from _dataprep import download_bytes, ROOT, sanitize_name


def flow_to_plan(plans):
    """Map flow id -> sanitized plan name (a flow not in any plan -> '_unplanned')."""
    m = {}
    for p in plans:
        pname = sanitize_name(p.get("name", f"plan_{p.get('id')}"))
        for f in (p.get("flows") or []):
            fid = f.get("id") if isinstance(f, dict) else f
            if fid is not None:
                m[fid] = pname
    return m


def main():
    tmp = ROOT / "output" / "temp"
    flows = json.loads((tmp / "flows.json").read_text(encoding="utf-8"))
    plans = json.loads((tmp / "plans.json").read_text(encoding="utf-8")) if (tmp / "plans.json").exists() else []
    pmap = flow_to_plan(plans)

    ok = fail = 0
    for fl in flows:
        fid = fl.get("id")
        plan = sanitize_name(pmap.get(fid, "_unplanned"))
        # one folder per flow: flows/<plan>/<flow>/recipe/  (the read-only recipe input)
        flow_dir = ROOT / "flows" / plan / sanitize_name(fl.get("name", f"flow_{fid}")) / "recipe"
        flow_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = download_bytes(f"v4/flows/{fid}/package")
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extractall(flow_dir)
            ok += 1
            print(f"  ok   flows/{plan}/{flow_dir.parent.name}/recipe")
        except Exception as e:  # keep going; one bad flow shouldn't halt the sweep
            fail += 1
            print(f"  FAIL flow {fid}: {e}")
    print(f"Extracted {ok} flows to flows/<plan>/<flow>/recipe/ ({fail} failed)")
    # If extraction fails with FileNotFoundError on deep names, shorten sanitize_name maxlen.


if __name__ == "__main__":
    main()
