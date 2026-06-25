# Python lane — when and how

For flows whose logic is unreadable or inexpressible as SQL. Python is a rare exception (SQL-first),
not a fallback — but default to SQL and escalate deliberately. When chosen, the deliverable is
`flows/<plan>/<flow>/<flow>.py` (same per-flow folder as the SQL lane), alongside its
`validation.sql`, `parity.md`, and `EXPLANATION.md`.

## Choose Python when the recipe has

- Multi-step regex/parsing chains, messy string surgery.
- Row-wise / iterative logic, fuzzy or probabilistic matching.
- ML / scoring / Vertex AI steps.
- External API or lookup enrichment.

If only ONE step needs Python, prefer **hybrid**: keep the bulk in SQL, isolate the hard
step in Python, stitch via the dependency graph.

## Transpile-first; native generation is a rare accelerator

Hand-transpile with the transform dictionary by default (`wrangle-to-python.md` Path B). Dataprep's
own Python generator (`POST /v4/outputObjects/<id>/wrangleToPython`; see `wrangle-to-python.md`
Path A) is a **rare optional accelerator** — DEPRECATED (R9.7), Enterprise-only, experimental
admin flag, **CSV-only**, **no multi-dataset operations**. Reach for it only when it cleanly
applies; most flows fall back to transpilation.

## Runtime: bigframes first

- **bigframes** (`bigframes.pandas`) — pandas API that pushes execution down to BigQuery.
  Preferred: scales, stays in-warehouse, output lands back in BigQuery naturally.
- **pandas** — only for genuinely small data where pulling locally is fine.
- **PySpark** — for large-scale flows targeting Spark/Dataproc, or when native gen emitted
  PySpark. The transform dictionary gives PySpark equivalents alongside pandas. Mind the three
  corruption risks — they bite hardest in Spark (timezone-naive `TimestampNTZType`, decimal≤38,
  coalesce-before-concat).

```python
import bigframes.pandas as bpd
from datetime import date
load_date = date.today()                # param/derived — never hard-code load/run dates
df = bpd.read_gbq("raw.customers")
# ... commented blocks, one per recipe step ...
# Write only to the disposable, write-guarded staging dataset:
df.to_gbq("dataprep_migration_staging.cust_enrich", if_exists="replace")
```

## Auth — gcloud not required

Use `google-cloud-bigquery` with **browser OAuth** via `pydata-google-auth` (or
`bigframes`/`pandas-gbq`'s built-in browser flow) — no `gcloud`/`bq` CLI dependency. The BigQuery
console and Dataform UI are valid fallbacks. Never hardcode credentials; never read `.env` (use
`.env.example` for variable names).

## Safety

Writes only to `dataprep_migration_staging` (write-guarded, default ~14-day table expiration,
deleted at teardown). Production/legacy are read-only — SELECT-only, never DDL/DML.

## Scheduling / cutover (after migration, for production runs)

A **plan** is the orchestration unit — preserve its order + schedule. Map it to either a Dataform
tag-group on a scheduled run, or a **Cloud Composer (Airflow) DAG** when Python steps and other
jobs need orchestrating together. Vertex AI pipeline if the flow includes ML/scoring. Keep one
choice consistent per LOB.

The SQL and Python lanes orchestrate together only when scheduled: the optional Dataform wrapper
builds the SQL models; the scheduler/Composer DAG triggers Python steps that read/write the same
BigQuery datasets, in plan order. (For one-off runs, each `<flow>.sql` / `<flow>.py` just runs on
its own — no orchestrator needed.)

## Parity

Identical to the SQL path — Python writes to `dataprep_migration_staging`, `@parity-auditor`
freezes the input then diffs the resulting BigQuery table against legacy. The harness doesn't
know or care it was Python.

## Gotchas

- Confirm written dtypes match legacy schema (schema diff catches this).
- Watch float precision vs the SQL path.
- Don't let a pandas index become a column in the output.
