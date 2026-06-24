# Dataform conventions

Layout, naming, and `.sqlx` patterns for the SQL target.

## Folder layout — per-flow folders

Gemini creates one **per-flow folder** at a time, canonical names, one flow end-to-end before the
next. A flow's SQL assets live together:

```
dataform/definitions/
  <plan>/<flow>/        <flow>.sqlx          the translated recipe (one CTE per recipe node)
                        <flow>.sql           standalone copy-paste console script (config stripped)
                        <flow>_parity.sqlx   the parity reconciliation assertion (deleted at cutover)
                        README.md            what the flow does + parity status
  sources/              declarations: raw source tables AND legacy Dataprep output tables (parity)
```

## Dual deliverable per flow (REQUIRED)

Every migrated flow produces **two artifacts** from the same SQL:

1. **Dataform model** `definitions/<plan>/<flow>/<flow>.sqlx` — carries the `config { ... }` block
   for repo compilation and orchestration.
2. **Standalone console script** — the same SQL with the **config block stripped** and a
   run-instructions header, saved to the flow folder as `<flow>.sql` and copied to
   `output/queries/<table>.sql`. Must run **as-is** in the BigQuery console with zero edits.

(Python lane mirrors this under `python/<plan>/<flow>/`; recipe input is read-only and gitignored
under `context/<plan>/<flow>/`. See SKILL.md for the full org map.)

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

## `.sqlx` config pattern

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

## Source declarations

```sql
-- definitions/sources/legacy_cust_clean.sqlx
config { type: "declaration", schema: "sales", name: "cust_clean" }
```

Declare both the raw inputs and the legacy Dataprep output (so parity can `ref()` it).

## Running

- `dataform compile` — validate the graph and SQL structure.
- `dataform run --tags plan:retail_nightly` — build one plan's flows into staging.
- `dataform run --tags parity` — run all reconciliation assertions.

`gcloud`/`bq` are **not required** — the Dataform UI or BigQuery console work; Python access uses
`google-cloud-bigquery` + browser OAuth (`pydata-google-auth`). Never hard-depend on the CLIs.

## Cutover & teardown (later, deliberate)

When a flow's parity has held green for the agreed window: repoint consumers to the migrated
table (or rename), delete the temporary `<flow>_parity.sqlx` assertion, retire the Dataprep flow.
A separate approved step — never automatic. At teardown, **delete the `dataprep_migration_staging`
dataset** (it also self-expires via the default table expiration).
