# Wrangle → BigQuery SQL — transform dictionary

The core asset. Each Dataprep Wrangle step maps to a BigQuery SQL pattern. Apply these;
don't improvise. **One CTE per recipe step.**

> **DRAFT.** Patterns below are from known Wrangle semantics. Validate each against a real
> recipe + green parity audit before trusting it. When you hit a step not listed here,
> translate carefully, add `-- TODO: verify`, and append the new mapping to this file.

> **Transpile-first.** The transform dictionary below is the primary engine. For BigQuery-source
> flows there's a **fast path — pushdown SQL**: Dataprep already compiles Wrangle into standard SQL
> in pushdown mode, so start from that SQL when you can get it and reshape into the commented
> CTE-per-step form below. Transpile from raw Wrangle when pushdown SQL isn't available. Carry the
> three corruption risks (timezone-naive temporal / decimal>38 / null-propagation — see
> `wrangle-to-python.md`) into every translation; they apply to SQL too.

## Conventions

- Each step becomes a CTE named `step<N>_<verb>` reading from the previous CTE.
- Comment above each CTE quotes the original Wrangle verbatim.
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
