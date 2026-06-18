# Wrangle → Python — transform dictionary

For flows that go to the Python target. **Transpile-first (Path B). Native generation (Path A)
is a rare optional accelerator, not the default.**

## Path B — Transpilation (PRIMARY)

Translate the raw Wrangle from `context/<plan>/<flow>/` directly using the registry below. This
is the owned, always-available engine and the cleanup layer for Path A. **One commented block
per recipe step, original Wrangle quoted.** Default runtime **bigframes**
(`bigframes.pandas`, pushes down to BigQuery); plain pandas for small data; **PySpark** for
large-scale Spark/Dataproc targets.

### Conventions
- Module docstring: source flow, why Python, output table, parity report path.
- Read: `df = bpd.read_gbq("dataset.table")`. Write only to the disposable staging dataset:
  `df.to_gbq("dataprep_migration_staging.<table>", if_exists="replace")`.

### Translation registry (Wrangle → Pandas / PySpark)

| Wrangle | Pandas | PySpark |
|---|---|---|
| `settype col:GameId type:'Integer'` | `df['GameId']=df['GameId'].astype(int)` | `df.withColumn('GameId', col('GameId').cast('integer'))` |
| `derive value:upper(c) as:'n'` | `df['n']=df['c'].str.upper()` | `df.withColumn('n', upper(col('c')))` |
| `derive dateformat` | `pd.to_datetime(df['t']).dt.strftime('%Y-%m-%d')` | `date_format(col('t'),'yyyy-MM-dd')` |
| `drop col:a,b` | `df.drop(columns=['a','b'])` | `df.drop('a','b')` |
| `join right on L=R type:right` | `pd.merge(a,b,left_on='L',right_on='R',how='right')` | `a.join(b, a.L==b.R, 'right')` |
| `derive conditional` | `np.where(df['x']==0, np.nan, df['y'])` | `when(col('x')==0, lit(None)).otherwise(col('y'))` |
| `keep row:cond` | `df=df[cond]` | `df.filter(cond)` |
| `delete row:cond` | `df=df[~(cond)]` | `df.filter(~(cond))` |
| `dedupe` | `df.drop_duplicates()` | `df.dropDuplicates()` |
| `aggregate SUM(x) group by g` | `df.groupby('g',as_index=False)['x'].sum()` | `df.groupBy('g').agg(sum('x'))` |
| `extractpatterns regex` | `df['out']=df['a'].str.extract(r'...')` | `regexp_extract(col('a'), r'...', 1)` |

## Path A — Native generation (RARE accelerator only)

Dataprep can emit Python itself. Reach for it **only when it cleanly applies**, then reshape into
the commented, one-block-per-step form above. Most flows hit a limit below and fall back to Path B.

- **API**: `POST /v4/outputObjects/<id>/wrangleToPython` → JSON payload with the compiled Python
  as a plain-text string. Target the output object's `id`.
- **Status & limits**: **DEPRECATED** (Release 9.7), **Enterprise-only**, experimental (admin
  must enable flag *"Wrangle to Python Conversion"*), **CSV inputs only**, and **no multi-dataset
  operations** (no joins/unions across datasets). Also weak on nested types (`MapType`/`ArrayType`)
  and function gaps (e.g. `NUMFORMAT`).
- **SDK note**: the `trifacta` PyPI package is stale/Alpha (last release 2021). Auth is via a
  `~/.trifacta.py.conf` file (NOT `tf.Client(url, token)`), and it carries the same feature flag
  and limits as the API. Treat as unreliable.

→ When any limit applies (the common case), use **Path B**.

## Three silent-corruption risks — ALWAYS defend against these

These are the top sources of value-level parity failures. Bake the fix into the translation.

1. **Temporal string drift.** Dataprep parses datetimes as strings and is timezone-naive;
   migrating to TZ-aware systems shifts dates. Map legacy datetimes to **`TimestampNTZType`**
   (Spark) / tz-naive datetime (pandas). Never run string ops on datetime values in Spark.
2. **Decimal precision truncation.** Alteryx `FixedDecimal` allows up to 50 digits; Spark/BQ
   cap at **38**. Scale high-precision columns to ≤38 digits or cast to string — else runtime
   error or silent precision loss.
3. **Null propagation.** Wrangle treats null == empty string; Python/Spark follow SQL-92
   (concat with null → null → wiped rows / skewed aggregates). Wrap concatenations in
   `coalesce(col, lit(''))` / `fillna('')` before joining strings.

## Gotchas (carry into parity)
- bigframes/pandas dtypes vs legacy BigQuery types — confirm in the schema tier.
- pandas index leaking into output — write with `if_exists="replace"`, check the column set.
