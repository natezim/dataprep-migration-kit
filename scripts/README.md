# Discovery scripts

One-command discovery: sweep every Dataprep flow/plan, export packages, compile run stats, and
build the status tracker + backlog. **READ-ONLY** — these only `GET` from Dataprep; they never modify a
flow, recipe, or output. All the production API gotchas are centralized in `_dataprep.py`
(pagination `limit=250`, `flowsFilter/plansFilter=all`, `latestPlanSnapshotRun`, name
sanitization, lock-safe writes). Full rationale: `.gemini/skills/dataprep-migration/references/dataprep-api.md`.

## Prereqs

- A local `.env` (copy `.env.example`) with `DATAPREP_API_BASE_URL` and `DATAPREP_API_TOKEN`.
  (Optional `GCP_PROJECT`.)
- Python 3.10+. Scripts 01–03 are stdlib-only. Script 04's Excel output needs
  `pip install -r ../requirements.txt` (pandas + openpyxl); without them it still writes
  `status/migration_status.csv` (the source of truth).

## Run order

```bash
cd scripts
python 01_sweep.py            # -> output/temp/flows.json, plans.json
python 02_download_unzip.py   # -> flows/<plan>/<flow>/recipe/   (exported packages)
python 03_job_stats.py        # -> output/temp/job_stats.json    (runs, durations, owners)
python 04_compile_catalog.py  # -> status/migration_status.csv (+ .xlsx) + status/backlog.md
```

Then in Gemini CLI, run `/dp:start` — it reads the status tracker/backlog and helps you migrate
one flow at a time. Re-running 04 preserves any status/signoff you've already set.

## Heads up

These were reconstructed from real production findings, so **smoke-test them against your
Dataprep version first** — JSON shapes (the `data` wrapper, `plan.flows`, the
`jobGroups → wrangledDataset → flow → id` path, `latestPlanSnapshotRun`) can vary by release.
If a shape differs, fix it once in the relevant script and commit — that's the hardening loop
(see `../MAINTAINING.md`).
