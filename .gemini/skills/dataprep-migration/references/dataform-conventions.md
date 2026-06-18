# Dataform conventions

Layout, naming, and `.sqlx` patterns for the SQL target.

## Folder layout — per-flow folders

Gemini creates one **per-flow folder** at a time, canonical names, one flow end-to-end before the
next. A flow's SQL assets live together:

```
dataform/definitions/
  <plan>/<flow>/        <flow>.sqlx          the translated recipe (one CTE per step)
                        <flow>_parity.sqlx   the parity reconciliation assertion (deleted at cutover)
                        README.md            what the flow does + parity status
  sources/              declarations: raw source tables AND legacy Dataprep output tables (parity)
```

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

## `.sqlx` config pattern

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
