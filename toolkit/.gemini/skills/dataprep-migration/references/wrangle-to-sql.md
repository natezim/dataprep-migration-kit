# Wrangle → BigQuery SQL — transform dictionary

The core asset. Each Dataprep Wrangle step maps to a BigQuery SQL pattern. Apply these;
don't improvise. **One CTE per recipe node.** BigQuery Standard SQL is the **primary and
default** lane — Python is a rare exception (see `wrangle-to-python.md`), used only when SQL
functionally cannot express the logic.

**The PRIMARY deliverable is a standalone single `.sql` file** —
`flows/<plan>/<flow>/<flow>.sql` — one self-contained, console-runnable script
(Create-Execute-Clean: `EXT_` external tables → `STG_` CTE graph → DROP). It must run **as-is**
in the BigQuery console with zero edits. A Dataform `.sqlx` wrapper is **optional**, only for
scheduled orchestration (see `dataform-conventions.md`).

## The "Create-Execute-Clean" lifecycle (GCS-CSV sources)

When a flow's sources are **GCS CSV files**, the whole pipeline is one self-contained,
sequential script with three phases. (If a source is already a **BigQuery table**, skip the
external-table create/drop and `ref()` it directly.)

**PHASE 1 — CREATE (mount sources).** One `CREATE OR REPLACE EXTERNAL TABLE` per GCS CSV,
prefixed `EXT_`, in the disposable `dataprep_migration_staging` dataset:

```sql
CREATE OR REPLACE EXTERNAL TABLE `proj.dataprep_migration_staging.EXT_USER_ALLOC` (
  Assigned_to STRING, Email STRING, User_ID STRING, License_key STRING, Created STRING
)
OPTIONS (
  format = 'CSV',
  uris = ['gs://my-bucket/Tableau/Tableau_User_allocations.csv'],
  skip_leading_rows = 1,
  quote = '"',
  field_delimiter = ',',
  allow_quoted_newlines = true   -- CRITICAL: quoted newlines otherwise truncate rows
);
```

`allow_quoted_newlines = true` is non-negotiable: unescaped newlines inside quoted fields
silently truncate rows without it.

**PHASE 2 — EXECUTE (transform).** One `CREATE OR REPLACE TABLE ... AS <CTE graph>` writing a
`STG_`-prefixed staging table. **One CTE per legacy recipe node**, each commented with its
original legacy recipe ID. **Never `SELECT *` in joins** — always coalesce/cast/alias columns
explicitly.

**PHASE 3 — CLEAN (pristine drop).** At the very bottom, `DROP EXTERNAL TABLE IF EXISTS` for
every external table created in Phase 1, leaving the schema pristine:

```sql
DROP EXTERNAL TABLE IF EXISTS `proj.dataprep_migration_staging.EXT_USER_ALLOC`;
```

**Naming:** `EXT_` for external (GCS) tables, `STG_` for staging output tables; all in the
disposable `dataprep_migration_staging` dataset.

## NO HARD-CODED VALUES — parameterize for automation

The standalone `.sql` is meant to run unattended, so **never bake in load/run dates or
environment-specific values**. Every value that changes between runs becomes a variable or
parameter. This is essential — a hard-coded `'2026-06-24'` silently rots the moment it ships.

- **Run/load dates** → `CURRENT_DATE()` / `CURRENT_TIMESTAMP()`, not a literal. A legacy
  `where load_date = '2026-06-24'` becomes `where load_date = CURRENT_DATE()` (or an offset).
- **Reusable constants** → `DECLARE` a typed variable at the top of the script and reference it:
  ```sql
  DECLARE run_date DATE DEFAULT CURRENT_DATE();
  DECLARE lookback_days INT64 DEFAULT 30;
  -- ... where event_date between date_sub(run_date, interval lookback_days day) and run_date
  ```
- **Console parameters** → use `@param` query parameters where the runner supplies values.
- **Dataform wrapper** → when an optional `.sqlx` exists, surface the same values as Dataform
  `vars` so the script and the wrapper stay in sync.
- **GCS URIs / project / dataset** that differ per env → `DECLARE` them too, or template via
  Dataform vars; don't scatter literals through the body.

> If you must keep a literal for Strict-Parity reproduction (e.g. a date the legacy run pinned),
> `DECLARE` it with a comment explaining why — keep it visible, not buried inline.

## HEAVY COMMENTING — make the script self-documenting

The deliverable is read by humans who own it after Gemini is gone. Over-comment, don't under.

- **Header block** at the top of every `.sql`: what the flow does, why it exists, when/how often
  it runs, the **source** tables/URIs, the **owner**, and the **parity** status (Strict/Clean +
  link to `parity.md`).
  ```sql
  -- =====================================================================
  -- Flow:    retail_nightly / cust_clean
  -- What:    Cleans + dedupes the nightly customer feed into STG_CUST_CLEAN.
  -- Why:     Replaces legacy Dataprep flow "Customer Clean" (read-only).
  -- When:    Nightly, after the raw load lands (~02:00). run_date = CURRENT_DATE().
  -- Source:  gs://my-bucket/retail/customers_*.csv  → EXT_CUSTOMERS
  -- Owner:   retail-data-eng@yourcompany.com
  -- Parity:  Strict — green as of 2026-06-20. See parity.md.
  -- =====================================================================
  ```
- **Inline comment on EVERY CTE**: quote the original Wrangle verbatim **and** note the original
  legacy recipe ID, so the graph maps back to the source flow.

> **DRAFT.** Patterns below are from known Wrangle semantics. Validate each against a real
> recipe + green parity audit before trusting it. When you hit a step not listed here,
> translate carefully, add `-- TODO: verify`, and append the new mapping to this file.

Each flow folder also ships a **validation.sql** (a query the *user* runs to compare new vs
legacy themselves — the team owns validation; don't rely on Gemini) and an **EXPLANATION.md**
(plain-English walkthrough). See `parity-harness.md`.

> **Transpile-first.** The transform dictionary below is the primary engine. For BigQuery-source
> flows there's a **fast path — pushdown SQL**: Dataprep already compiles Wrangle into standard SQL
> in pushdown mode, so start from that SQL when you can get it and reshape into the commented
> CTE-per-step form below. Transpile from raw Wrangle when pushdown SQL isn't available. Carry the
> five corruption risks (tz-naive temporal, decimal>38, null-propagation, date-midnight, trailing-newline — see
> `wrangle-to-python.md`) into every translation; they apply to SQL too.

## Conventions

- **One CTE per legacy recipe node**, named `step<N>_<verb>`, reading from the previous CTE.
- Comment above each CTE quotes the original Wrangle verbatim **and notes the original legacy
  recipe ID** so the graph maps back to the source flow.
- **Never `SELECT *` in joins** — coalesce/cast/alias every column explicitly. (`select * replace`
  / `except` are fine for single-source column edits, not for joins.)
- `select * replace(...)` keeps column order when only changing a few columns.
- `select * except(...)` drops columns cleanly.

## Step mappings

| Wrangle step | BigQuery SQL pattern |
|---|---|
| `import dataset X` | `select <cols> from ${ref("X")}` (first CTE / source) |
| `set col: <expr>` (modify) | `select * replace(<sql_expr> as col) from prev` |
| `derive value: <expr> as 'new'` | `select *, <sql_expr> as new from prev` |
| `keep row: <cond>` | `select * from prev where <cond>` |
| `delete row: <cond>` | `select * from prev where not (<cond>)` |
| `filter: ISMISSING(col)` → delete | `select * from prev where col is not null` |
| `drop col: a, b` | `select * except(a, b) from prev` |
| `rename col: a to 'b'` | `select * except(a), a as b from prev` (or `replace`) |
| `keep col: a, b, c` | `select a, b, c from prev` |
| `dedupe` (all columns) | `select distinct * from prev` |
| `dedupe on: key` | `qualify row_number() over(partition by key order by ...) = 1` |
| `join with Y on a = b, type: left` | `left join ${ref("Y")} on prev.a = Y.b` |
| `union Y` | `select <aligned cols> from prev union all select <aligned> from ${ref("Y")}` |
| `aggregate value: SUM(x) group by: g` | `select g, sum(x) as ... from prev group by g` |
| `pivot col: k value: SUM(v)` | conditional agg: `sum(case when k='...' then v end) as ...` (or `PIVOT`) |
| `unpivot` | `UNPIVOT` operator, or `union all` per source column |
| `replace col: a with: 'x' on: 'y'` | `replace(a, 'y', 'x')` |
| `extractpatterns col: a on: <regex>` | `regexp_extract(a, r'<regex>')` |
| `valuestonull col: a on: '...'` | `nullif(a, '...')` or `case when ... then null else a end` |
| `merge col: a, b delimiter: '-'` | `concat(a, '-', b)` |
| `split col: a on: ',' ` | `split(a, ',')` → array, or `regexp_extract_all` |

## Function translation (Wrangle → BigQuery)

| Wrangle | BigQuery |
|---|---|
| `TRIM(x)` | `trim(x)` |
| `UPPER/LOWER(x)` | `upper(x)` / `lower(x)` |
| `LEN(x)` | `length(x)` |
| `ISMISSING(x)` | `x is null` |
| `IFMISSING(x, y)` | `ifnull(x, y)` / `coalesce(x, y)` |
| `IF(c, a, b)` | `if(c, a, b)` / `case when c then a else b end` |
| `DATEFORMAT(d, fmt)` | `format_date(fmt_bq, d)` (translate the format tokens!) |
| `PARSEDATE / DATE(...)` | `parse_date` / `parse_datetime` / `safe.parse_*` |
| `ROUND(x, n)` | `round(x, n)` |
| string concat `+` | `concat(...)` / `||` |

## Known gotchas (carry into parity)

- **Type coercion**: Dataprep is loose with string↔number↔date; BigQuery is strict. Use
  `safe_cast` / `safe.parse_*` and verify nulls in the volume diff.
- **Null handling**: Wrangle `ISMISSING` covers null AND empty string in some contexts —
  check whether `''` should also be treated as missing.
- **Float formatting / rounding**: a frequent value-diff source. Confirm precision against legacy.
- **Date format tokens** differ between Wrangle and BigQuery `format_date` — translate, don't copy.
- **Ordering**: Dataprep may emit rows in input order; BigQuery does not guarantee order. Parity
  reconciles on key, not row position — don't rely on ORDER BY for correctness.
