# SQL conventions — the `<flow>.sql` deliverable (+ optional Dataform)

Layout, naming, and SQL patterns for the SQL target. **The primary deliverable is one
self-contained, console-runnable `<flow>.sql`.** A Dataform `.sqlx` wrapper is **OPTIONAL** —
only for scheduled orchestration.

## Folder layout — one folder per flow

Gemini creates one **per-flow folder** at a time, canonical names, one flow end-to-end before the
next. Everything for a flow lives together under `flows/<plan>/<flow>/`:

```
flows/
  <plan>/
    README.md                  what this plan does + per-flow parity status
    <flow>/
      <flow>.sql               PRIMARY deliverable — self-contained Create-Execute-Clean script
      validation.sql           user runs this to compare new vs legacy
      EXPLANATION.md           plain-language walkthrough of the flow + its SQL
      parity.md                parity report (strict/clean verdict)
      recipe/                  read-only exported Dataprep recipe (gitignored input)
      <flow>.sqlx              OPTIONAL — Dataform wrapper for scheduled orchestration
      <flow>.py                RARE — only when the flow goes the Python lane
  sources/                     OPTIONAL declarations (only if you use Dataform): raw + legacy tables
```

(Python lane reuses the same folder — `flows/<plan>/<flow>/<flow>.py`. See SKILL.md for the full
org map.)

## Primary deliverable — `<flow>.sql` (REQUIRED)

One **self-contained, console-runnable** script that runs **as-is** in the BigQuery console with
zero edits. It is the unified **Create-Execute-Clean** pipeline in one file: DDL mount + DML
transform + DDL drop (see `wrangle-to-sql.md`).

- **NO HARD-CODED VALUES.** Load/run dates and env-specific values become variables/params, never
  literals baked into the SQL. Use `DECLARE` + `CURRENT_DATE()` (or query parameters) at the top:
  ```sql
  DECLARE load_date DATE DEFAULT CURRENT_DATE();      -- override for a backfill; never hard-code
  DECLARE gcs_uri   STRING DEFAULT 'gs://bucket/path/*.csv';
  ```
- **HEAVY COMMENTING.** A file header (what the flow does, source → target, parity status) plus
  **one inline comment per CTE** explaining the recipe step it implements.
- Each flow also ships `validation.sql` (the user runs it to diff new vs legacy — see
  `parity-harness.md`) and `EXPLANATION.md` (plain-language walkthrough).

## Optional Dataform `.sqlx` wrapper (scheduled orchestration only)

`.sqlx` is **not required**. Add it only when the flow needs to run on a schedule inside a Dataform
repo. It wraps the **same SQL** from `<flow>.sql` in a `config { ... }` block — no logic changes.
The standalone `<flow>.sql` always stays the source of truth; the `.sqlx` is a thin orchestration
shell. In Dataform, replace `DECLARE`d literals with Dataform vars (`${dataform.projectConfig.vars.load_date}`)
so there are still no hard-coded values.

## Naming

- **Model names must be unique** across the project — schema-qualify / make them plan-aware
  (e.g. `<plan>_<flow>`) so two flows never collide.
- Legacy source declaration name = `legacy_<output_table>`.

## Staging dataset — disposable, self-cleaning

All migrated output lands in **one disposable staging dataset** `dataprep_migration_staging`,
created with a **default table expiration (~14 days)** so it self-cleans, and **deleted entirely
at teardown**.

- **WRITE-GUARD:** every write must target `dataprep_migration_staging`. Refuse any write aimed
  at another dataset. Production/legacy are **read-only (SELECT-only)** — never DDL/DML there.
- **EXT_/STG_ naming:** GCS external tables are prefixed `EXT_`, staging output tables `STG_`.
- **External-table drop hygiene:** any `EXT_` table created to mount a GCS CSV must be dropped
  (`DROP EXTERNAL TABLE IF EXISTS`) at the very bottom of the same script — leave the schema
  pristine (the "Create-Execute-Clean" lifecycle; see `wrangle-to-sql.md`).

## Optional `.sqlx` config pattern

For the unified Create-Execute-Clean pipeline (DDL mount + DML transform + DDL drop in one
script), use `type: "operations"` with `hasOutput: true`:

```sql
config {
  type: "operations",                         -- single sequential DDL/DML/DDL script
  hasOutput: true,                            -- Dataform treats STG_ output as a buildable table
  database: "my-gcp-project",
  schema: "dataprep_migration_staging",       -- disposable staging dataset (write-guarded)
  name: "STG_RETAIL_CUST_CLEAN",              -- unique, plan-aware, STG_-prefixed
  tags: ["plan:retail_nightly", "lob:retail"]
}
```

For a pure set-based model (no GCS mounting — all sources are BigQuery tables), a plain
`type: "table"` model with inline assertions is fine:

```sql
config {
  type: "table",                              -- or "view" / "incremental"
  schema: "dataprep_migration_staging",       -- disposable staging dataset (write-guarded)
  name: "retail_cust_clean",                  -- unique, plan-aware model name
  tags: ["plan:retail_nightly", "lob:retail"],
  assertions: {
    uniqueKey: ["customer_id"],
    nonNull: ["customer_id", "email"],
    rowConditions: ["signup_dt <= current_date()"]
  }
}
```

- `tags` let you run/track by plan or business unit: `dataform run --tags lob:retail`. Use
  `plan:<name>` (orchestration unit) and `lob:<name>`.
- Inline `assertions` encode the data-quality guarantees the recipe implied.
- Dependencies via `${ref("upstream_model")}` — Dataform orders the run automatically.

## Source declarations (optional — Dataform path only)

```sql
-- flows/sources/legacy_cust_clean.sqlx
config { type: "declaration", schema: "sales", name: "cust_clean" }
```

Declare both the raw inputs and the legacy Dataprep output (so parity can `ref()` it).

## Running

- **Console (primary):** paste `<flow>.sql` into the BigQuery console and run — zero edits.
- `dataform compile` — validate the graph and SQL structure (only if you added `.sqlx`).
- `dataform run --tags plan:retail_nightly` — build one plan's flows into staging.
- `dataform run --tags parity` — run all reconciliation assertions.

`gcloud`/`bq` are **not required** — the Dataform UI or BigQuery console work; Python access uses
`google-cloud-bigquery` + browser OAuth (`pydata-google-auth`). Never hard-depend on the CLIs.

## Cutover & teardown (later, deliberate)

When a flow's parity has held green for the agreed window: repoint consumers to the migrated
table (or rename), delete any temporary parity assertion, retire the Dataprep flow.
A separate approved step — never automatic. At teardown, **delete the `dataprep_migration_staging`
dataset** (it also self-expires via the default table expiration).
