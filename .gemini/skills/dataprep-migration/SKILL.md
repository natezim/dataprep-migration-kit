---
name: dataprep-migration
description: >
  Migrate Dataprep (Trifacta) flows into BigQuery SQL (Dataform) or Python. Use whenever the
  user is translating an exported Dataprep recipe, profiling flows for migration, choosing a
  SQL-vs-Python target, writing the migrated model, or running a parity audit against the
  legacy Dataprep output table. Covers Wrangle→SQL and Wrangle→Python transform mappings,
  recipe JSON anatomy, Dataform conventions, and the reconciliation harness.
---

# Dataprep Migration

Method for turning Dataprep recipes into maintainable BigQuery assets, proven against the
legacy output. The whole approach rests on one fact: **Wrangle is a finite DSL, so this is
transpilation** — apply the reviewed mapping, don't reinvent per flow.

**One flow at a time, end-to-end, before the next.** One flow = one branch = one session =
one commit. Bulk migration is refused; only discovery (read-only) is bulk. Gemini creates one
per-flow folder at a time, with canonical names.

## The method (per flow)

1. **Inventory** the flow package — sources, output(s), ordered steps, DAG deps, complexity,
   target. Package comes via the Dataprep API (`GET /v4/flows/{id}/package`) OR the UI
   "Export Flow" (identical ZIP) — **API-optional**. (`recipe-anatomy.md` for package/DAG.)
2. **Pick the target — SQL-first.** BigQuery Standard SQL (Dataform) is the primary lane; Python
   is a **rare exception** only when SQL can't express the logic. Produce the **dual deliverable**:
   a Dataform `.sqlx` AND a standalone copy-paste `.sql`.
3. **Translate, transpile-first** — apply the transform dictionary and reuse pushdown SQL for
   BigQuery-source flows. Use the **Create-Execute-Clean** lifecycle for GCS-CSV sources (mount
   `EXT_*` external tables with `allow_quoted_newlines=true` → build `STG_*` via a CTE-per-recipe-node
   graph → DROP externals). Native code-gen (`wrangleToPython`) is a **rare accelerator only**.
   Apply the five corruption fixes.
4. **Compile & dry-run** — catch structure/syntax/cost before a real run.
5. **Parity audit** — freeze the input (snapshot/time-travel), run into staging, 4-tier diff vs
   legacy (schema → row count → MD5 row-hash → cell-level), exact match in **Strict Parity** mode
   (reproduce legacy exactly, incl. its bugs). Clean Promotion is a documented post-pass.
6. **Promote** — green parity → merge + log. Run side-by-side over a validation window; legacy
   never touched.

## Transpile-first; native code-gen is a rare accelerator

Primary path is **our transform dictionary** plus reused pushdown SQL — it's accurate, owned,
and always available. Dataprep's own Python generator is an optional accelerator, not "native
first":
- **Native Python code-gen**: `POST /v4/outputObjects/<id>/wrangleToPython`. **Deprecated**
  (Release 9.7), **Enterprise-only**, experimental (admin flag *"Wrangle to Python Conversion"*),
  **CSV-inputs-only**, **no multi-dataset operations**. Use only when it cleanly applies;
  otherwise transpile. Always reshape its output to commented, one-block-per-step form.
- **SQL**: BigQuery-source flows already compile Wrangle → standard SQL in pushdown mode — reuse
  that as the starting point.
- The transform dictionary is the primary engine and the cleanup layer either way.

## SQL vs Python decision rule

| Signal in the recipe | Target |
|---|---|
| Filters, joins, aggregations, pivots, dedupe, simple derivations | **SQL** |
| Window/analytic logic expressible in BigQuery | **SQL** |
| Multi-step regex/parsing chains, messy string surgery | **Python** |
| Row-wise / iterative logic, fuzzy or probabilistic matching | **Python** |
| ML, scoring, Vertex AI steps, external API/lookup enrichment | **Python** |
| Mostly SQL with one hard step | **Hybrid** (SQL + one Python step) |

SQL is the default; Python is a rare exception — and say why in the file header when used.

## The five corruption fixes (bake into every translation)

1. **Timezone-naive temporals** — keep tz-naive (`TimestampNTZType` / naive datetime); never run string ops on datetimes.
2. **Decimal precision** — cap at 38; beyond that, cast to string (else runtime error / silent loss).
3. **Null propagation** — `coalesce`/`nullif`/`fillna('')` before any string concat or join.
4. **Date midnight** — `datetime_trunc(safe_cast(x as DATETIME), DAY)` to match Dataprep's `yyyy-MM-dd`.
5. **Trailing newlines** in quoted GCS fields — reproduce raw (strict parity) or `trim(regexp_replace(col,'^"|"$',''))` (clean).

## Output shape (non-negotiable for maintainability)

- **Dual deliverable:** a Dataform `.sqlx` (`type:"operations", hasOutput:true`) in
  `definitions/<plan>/<flow>/` AND a copy-paste `.sql` (config stripped) in `output/queries/<table>.sql`.
- One **CTE per legacy recipe node**, commented with its recipe ID; no `SELECT *` in joins.
- Tag every model `plan:<name>` and `lob:<name>`. Add assertions (uniqueKey, nonNull) inline.
- Per-flow folders, canonical names (≤60 chars, no flow-IDs — Windows MAX_PATH). See `dataform-conventions.md`.

## Parity is target-agnostic + frozen-input

The reconciliation compares two BigQuery tables; it does not matter whether SQL or Python
produced the new one — the harness is identical, so Python costs nothing in auditability.
Always **freeze the input** first (BigQuery time-travel / snapshot) so migrated code and legacy
Dataprep see identical input, killing input drift. Writes go only to the disposable staging
dataset `dataprep_migration_staging`; legacy/prod are read-only (SELECT-only).

## Reference files — load as needed

| File | Load when… |
|---|---|
| `references/dataprep-api.md` | Calling the Dataprep API: pagination (`limit=250`), `flowsFilter/plansFilter=all`, `latestPlanSnapshotRun`, jobGroups + creator/durations |
| `references/recipe-anatomy.md` | Reading/parsing exported flow packages; mapping structure to steps |
| `references/wrangle-to-sql.md` | Wrangle → BigQuery SQL + the Create-Execute-Clean external-table pattern |
| `references/wrangle-to-python.md` | Wrangle → pandas/PySpark (rare); the five corruption fixes |
| `references/dataform-conventions.md` | Folder layout, dual deliverable, `.sqlx` operations config, EXT_/STG_ naming |
| `references/python-lane.md` | The rare Python path: bigframes vs pandas, auth, scheduling |
| `references/parity-harness.md` | Frozen input, 4-tier diff, Strict-Parity vs Clean-Promotion |
| `references/windows-onedrive.md` | MAX_PATH name sanitization, OneDrive file-lock fallback writes |

> **Build status:** these references are drafted from known Wrangle semantics and get
> hardened against real exported recipes during the pilot. Treat any pattern as
> provisional until validated by a green parity audit on a real flow.
