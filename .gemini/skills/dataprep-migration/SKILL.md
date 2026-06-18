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
2. **Pick the target** — SQL (Dataform) by default; Python (bigframes/pandas/PySpark) first-class
   for complex logic; hybrid allowed (see below).
3. **Translate, transpile-first** — apply the transform dictionary (Wrangle → SQL/pandas/PySpark)
   and reuse pushdown SQL for BigQuery-source flows. Native code-gen
   (`wrangleToPython`) is a **rare optional accelerator**, not the default — use only when it
   cleanly applies. Reshape into one CTE / one Python block per step, original Wrangle quoted.
   Apply the three corruption fixes.
4. **Compile & dry-run** — catch structure/syntax/cost before a real run.
5. **Parity audit** — freeze the input (snapshot/time-travel), run into staging, 4-tier diff vs
   legacy (schema → row count → MD5 row-hash → cell-level), exact match.
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

Default to SQL for readability. Escalate to Python only when SQL would be unreadable or
can't express the logic — and say why in the file header.

## The three corruption fixes (bake into every translation)

1. **Timezone-naive temporals** — map legacy datetimes to `TimestampNTZType` (Spark) /
   tz-naive datetime (pandas); never run string ops on datetimes.
2. **Decimal precision** — cap at 38; beyond that, cast to string (else runtime error / silent loss).
3. **Null propagation** — `coalesce` / `fillna('')` before any string concat (Wrangle null == '').

## Output shape (non-negotiable for maintainability)

- One block per recipe step; original Wrangle quoted above it.
- A reviewer must be able to line up block N with recipe step N.
- Tag every model `plan:<name>` and `lob:<name>`. Add assertions (uniqueKey, nonNull) inline.
- Per-flow folders, canonical names: SQL `definitions/<plan>/<flow>/`, Python
  `python/<plan>/<flow>/`. See `dataform-conventions.md`.

## Parity is target-agnostic + frozen-input

The reconciliation compares two BigQuery tables; it does not matter whether SQL or Python
produced the new one — the harness is identical, so Python costs nothing in auditability.
Always **freeze the input** first (BigQuery time-travel / snapshot) so migrated code and legacy
Dataprep see identical input, killing input drift. Writes go only to the disposable staging
dataset `dataprep_migration_staging`; legacy/prod are read-only (SELECT-only).

## Reference files — load as needed

| File | Load when… |
|---|---|
| `references/recipe-anatomy.md` | Reading/parsing exported recipe JSON; mapping its structure to steps |
| `references/wrangle-to-sql.md` | Translating recipe steps to BigQuery SQL (the transform dictionary) |
| `references/wrangle-to-python.md` | Translating steps to pandas / BigQuery DataFrames |
| `references/dataform-conventions.md` | Folder layout, naming, tags, `.sqlx` config & assertion patterns |
| `references/python-lane.md` | Choosing/running Python: bigframes vs pandas, auth, scheduling |
| `references/parity-harness.md` | Building the schema/volume/value reconciliation checks |

> **Build status:** these references are drafted from known Wrangle semantics and get
> hardened against real exported recipes during the pilot. Treat any pattern as
> provisional until validated by a green parity audit on a real flow.
