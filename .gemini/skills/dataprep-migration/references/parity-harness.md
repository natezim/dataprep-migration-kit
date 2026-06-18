# Parity harness — the self-audit (frozen input + 4 tiers)

Prove a migrated table matches its legacy Dataprep output. Run tiers in order; stop drilling
once a tier passes cleanly, escalate to the next when it doesn't. **Exact-match bar.**
Target-agnostic: compares two BigQuery tables regardless of SQL vs Python origin.

`<new>` = `dataprep_migration_staging.<table>`. `<legacy>` = the Dataprep output table.
Legacy/prod are **read-only (SELECT-only — never DDL/DML)**; the migrated table writes only to
the disposable `dataprep_migration_staging`. Always dry-run + set a max-bytes guardrail first.

## Step 0 — FREEZE THE INPUT (do this first)

Snapshot the source via **BigQuery time-travel** (`FOR SYSTEM_TIME AS OF <ts>`) or a one-off
snapshot table so the migrated code **and** the legacy Dataprep run see the **identical input**.
This kills input drift — the most common cause of false parity failures when the source moves
between the two runs. Pin both runs to the frozen snapshot.

## Normalize legit differences first

Before comparing, normalize differences that are cosmetic / expected so they don't false-fail:
**column order, float rounding, row order, timezone, surrogate keys / generated timestamps.**
A diff that survives normalization is a real diff.

## Tier 1 — Schema parity

Column names + datatypes on both sides; flag renamed/dropped/added/type-changed. Pay special
attention to float/decimal precision and temporal types (the corruption risks — see
`wrangle-to-python.md`).

```sql
select column_name, data_type, 'new' src
from `dataprep_migration_staging`.INFORMATION_SCHEMA.COLUMNS where table_name='<table>'
union all
select column_name, data_type, 'legacy'
from `<legacy_dataset>`.INFORMATION_SCHEMA.COLUMNS where table_name='<table>';
```

## Tier 2 — Row count

```sql
select (select count(*) from `<new>`) as new_rows,
       (select count(*) from `<legacy>`) as legacy_rows;
```
Mismatch ⇒ a filter / join / dedupe step diverged. Drill to Tier 4.

## Tier 3 — Row-level checksum (the efficient deep check)

Hash every row (all columns concatenated, in a fixed column order) and compare the multiset of
hashes. Scales far better than a full JSON outer-join on large tables.

```sql
with n as (
  select to_hex(md5(to_json_string(t))) as h from `<new>`  t
), l as (
  select to_hex(md5(to_json_string(t))) as h from `<legacy>` t
)
select
  (select count(*) from n) as new_rows,
  (select count(*) from l) as legacy_rows,
  (select count(*) from (select h from n except distinct select h from l)) as only_in_new,
  (select count(*) from (select h from l except distinct select h from n)) as only_in_legacy;
```
`to_json_string(t)` gives a stable, type-aware serialization. If both `only_in_*` are 0 →
**exact match, verified.** Normalize float formatting / column order first so cosmetic
differences don't false-fail.

## Tier 4 — Cell-level discrepancy scan

Only when Tier 3 finds diffs. Join on the natural/primary key, report the exact coordinates
(key, column) that diverge — bounded sample, structure only, never dump PII.

```sql
select n.<key>,
  array_to_string(array(
    select c from unnest([
      if(n.a is distinct from l.a, 'a', null),
      if(n.b is distinct from l.b, 'b', null)   -- one per column
    ]) c where c is not null), ', ') as differing_columns
from `<new>` n join `<legacy>` l using (<key>)
where to_json_string(n) != to_json_string(l)
limit 50;
```
Map each differing column back to the recipe step that produces it — that's the step to fix.
Most cell-level diffs trace to the three corruption risks (temporal drift, decimal >38, null
propagation).

## As a Dataform assertion (preferred during the migration window)

Wrap Tier 3 as an assertion so it runs in the graph and fails the build on any diff:

```sql
-- definitions/<plan>/cust_clean/cust_clean_parity.sqlx
config { type: "assertion", tags: ["parity", "plan:retail_nightly", "lob:retail"] }
with n as (select to_hex(md5(to_json_string(t))) h from ${ref("cust_clean")} t),
     l as (select to_hex(md5(to_json_string(t))) h from ${ref("legacy_cust_clean")} t)
select h from n except distinct select h from l        -- FAILS if any row in new isn't in legacy
union all
select h from l except distinct select h from n;       -- ...or any legacy row missing from new
```
`dataform run --tags parity` runs them all. Zero rows = exact match. Delete at cutover.

## Verdict

PASS only if Tiers 1–3 are clean (or every diff is documented + approved). On FAIL, Tier 4
gives the coordinates; trace to the recipe step. Run new + legacy **side-by-side** over a
validation window before cutover.
