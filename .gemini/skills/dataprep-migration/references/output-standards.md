# Output standards — what every migrated flow must look like

Non-negotiable. `@governance` checks these; `/dp:signoff` won't pass a flow that fails them.
Everything lives in `flows/<plan>/<flow>/`.

## 1. One self-contained SQL file (the primary deliverable)

`flows/<plan>/<flow>/<flow>.sql` — a single, console-runnable BigQuery file using the
**Create-Execute-Clean** lifecycle:

```sql
-- Header (see §3) ...
-- PART 1 — REGISTER GCS SOURCES (temp external tables)
CREATE OR REPLACE EXTERNAL TABLE `proj.dataprep_migration_staging.EXT_orders` ( ... )
OPTIONS ( format='CSV', uris=['gs://.../orders.csv'], skip_leading_rows=1,
          allow_quoted_newlines=true );
-- PART 2 — TRANSFORM (one CTE per recipe node, each commented)
CREATE OR REPLACE TABLE `proj.dataprep_migration_staging.STG_orders` AS
with cleaned as ( /* recipe node 3: trim + cast */ ... )
select ... from cleaned;
-- PART 3 — CLEAN UP
DROP EXTERNAL TABLE IF EXISTS `proj.dataprep_migration_staging.EXT_orders`;
```

A `<flow>.sqlx` Dataform wrapper is OPTIONAL — only when you want scheduled orchestration.

## 2. No hard-coded values

Anything that varies per run is a variable/parameter — **especially load/run dates**, project
ids, and bucket paths. This is mandatory for automation.

```sql
DECLARE run_date DATE DEFAULT CURRENT_DATE();      -- not a literal '2026-06-18'
-- or a query parameter @run_date, or a Dataform var ${dataform.projectConfig.vars.run_date}
```
Grep your file for literal dates / ids before signoff — a governance blocker if found.

## 3. Heavy commenting

- **File header** (top of `<flow>.sql`): what it does, why, date last modified, source(s),
  owner, target table, parity result, and "how to make common changes."
- **Inline**: one comment on every CTE tracing to its original recipe node/ID. No un-commented
  logic. No `SELECT *` in joins — coalesce/cast/alias explicitly.

The point: a maintainer (or Gemini, later) can read it cold and troubleshoot/extend it.

## 4. Independent validation (the team owns it)

Every flow ships, alongside the `.sql`:

- **`validation.sql`** — a query the **user runs themselves** to compare new vs legacy and SEE
  the result (e.g. the row-hash diff / a sample of mismatches). Self-contained, copy-paste.
- **`EXPLANATION.md`** — plain-English: what the flow does, why each major step, how to maintain
  it, and the parity result. So the team validates without taking Gemini's word for it.
- **`parity.md`** — the audit evidence (frozen-input 4-tier Strict-Parity result).

## Per-flow deliverables checklist

`flows/<plan>/<flow>/`: `<flow>.sql` (required) · `validation.sql` · `EXPLANATION.md` ·
`parity.md` · `governance.md` · optional `<flow>.sqlx` · `recipe/` (read-only input).
