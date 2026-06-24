# Dataprep Migration Kit — Guide

How this toolkit works, and how to use it to migrate Dataprep (Trifacta) flows into
BigQuery SQL — repeatably, with readable output and an automatic audit that proves each
migration matches what Dataprep produced. **The team owns the migration; Gemini assists,
humans validate and sign off.**

Read this once before you migrate your first flow. It's the source of truth for the method.

---

## 1. What problem this solves

We have ~100 prebuilt Dataprep flows. We want them off Dataprep and into our own,
maintainable assets in BigQuery — without:

- losing logic in translation,
- producing 100 differently-shaped one-off scripts nobody can maintain, or
- having to manually prove each new table matches the old one.

Lines of business will eventually run this themselves, so the output has to be readable
and the process has to be a repeatable golden path, not artisanal work.

## 2. The core idea (why this is tractable)

A Dataprep flow is not free-form code. It's a **recipe** — an ordered list of steps
written in **Wrangle**, a finite DSL (`derive`/`set`, `keep`/`filter`, `join`,
`aggregate`, `pivot`/`unpivot`, `dedupe`, `replace`, `extractpatterns`, `valuestonull`,
…). Because the vocabulary is finite, migration is **transpilation**: each Wrangle step
maps to a known SQL (or Python) pattern.

That's what makes output consistent. Gemini isn't inventing SQL per flow — it's applying
a reviewed mapping from the **transform dictionary**. One hundred flows come out looking
like they were written by the same careful person.

## 3. SQL-first, one self-contained file per flow

**BigQuery Standard SQL is the primary lane.** Every flow targets SQL unless SQL literally
cannot express the logic. The **primary deliverable is a single self-contained
`flows/<plan>/<flow>/<flow>.sql`** — one console-runnable file using the
**Create-Execute-Clean** lifecycle (mount GCS CSVs as `EXT_` external tables → build `STG_`
via a CTE-per-recipe-node graph → DROP the externals). No orchestration platform required to
run it.

A **`<flow>.sqlx` Dataform wrapper is optional** — add it only when you want scheduled
orchestration. Python remains a rare exception, only when SQL truly cannot express the logic.

| Deliverable | Role |
|---|---|
| **`<flow>.sql`** | Primary — self-contained, copy-paste into the BigQuery console |
| `<flow>.sqlx` | Optional — Dataform wrapper for scheduled runs |
| Python | Rare exception — heavy multi-step regex, row-wise/iterative, fuzzy match, ML/Vertex |

**The decision rule lives in two places** and is applied automatically:
`GEMINI.md` (project root) and `.gemini/skills/dataprep-migration/SKILL.md`.

Key property: **the parity audit is target-agnostic.** It compares two BigQuery tables —
it does not care how the new one was produced. So the SQL/SQLX/Python choice costs you
nothing in auditability.

## 4. Why Dataform for the SQL target

- **Dependency graph** — flows that feed other flows become `ref()` calls; Dataform builds
  and runs them in the right order.
- **Assertions = the self-audit, built in** — our parity checks are native Dataform
  assertions, version-controlled in git.
- **Readable & maintainable** — plain `.sqlx` in a repo. An LOB analyst can read it.
- **Google-native and free** — runs inside BigQuery; no extra platform.

## 5. The pipeline — what happens to every flow

This is the repeatable golden path. The `/dp:migrate` command runs the migration steps; you
can also run any agent by hand. The final promotion to Productionized is a separate human
step (`/dp:signoff`).

```
  flows/<plan>/<flow>/recipe/
        │
   1. INVENTORY      @flow-inventory  → parse flow package: sources, outputs, every step,
        │                               DAG deps, complexity, TARGET (SQL).
   2. TRANSLATE      @recipe-translator → transpile via the transform dictionary into ONE
        │                               self-contained <flow>.sql; one commented CTE per step;
        │                               no hard-coded values (DECLARE / CURRENT_DATE() / params)
   3. COMPILE        BigQuery dry-run (cost & syntax); dataform compile if a .sqlx wrapper exists
        │
   4. PARITY AUDIT   @parity-auditor  → run into the disposable staging dataset, 4-tier diff
        │                               vs legacy on a frozen input
        │                               (schema → rows → MD5 hash → cell). Exact-match bar.
   5. GOVERNANCE     @governance      → review against the checklist (no hardcoding, comments,
        │                               single file, strict parity green, validation.sql +
        │                               EXPLANATION.md present, naming, read-only) → report.
   6. REPORT         parity.md + EXPLANATION.md + validation.sql land in flows/<plan>/<flow>/.
        │                               Fail → shows the diverging step.
   ── SIGNOFF        /dp:signoff → human attests they validated it → status: Productionized.
                                  Legacy untouched throughout.
```

### Step 1 — Inventory
`@flow-inventory` reads the exported **flow package** (a ZIP from the Dataprep API
`GET /v4/flows/{id}/package`, or the identical ZIP from the UI **"Export Flow"** button —
the API is the fast path but is **optional**; LOB users with no API access export from the
UI). The package contains `flow.json`, `recipes/`, `inputs/`, `outputs/`. It emits, per flow:
source tables, output table(s), the ordered step list, which Wrangle transforms are used, a
complexity class, and the **recommended target**. It builds the dependency graph from the
package's flow nodes + edges
(`inputFlownode.id → outputFlownode.id`), and detects **BigQuery-pushdown vs Dataflow-mode**
flows — pushdown flows are near-trivial (SQL already exists); Dataflow-mode flows with custom
logic are the hard minority. Across all flows this produces the ranked `status/backlog.md` and
the `status/migration_status.csv` tracker. See `references/recipe-anatomy.md` for the package
schema. Discovery is read-only and the **only** bulk-allowed step.

### Step 2 — Translate (transpile-first)
`@recipe-translator` is the workhorse. Because Wrangle is a finite declarative DSL, translation
is **transpilation**: it applies the reviewed **transform dictionary** (one known SQL/Python
pattern per step) and reuses **pushdown SQL** for BigQuery-source flows. That dictionary plus
pushdown reuse is the engine — not a from-scratch rewrite.

**Native gen is a rare optional accelerator, not the default.** Dataprep can emit Python via
`POST /v4/outputObjects/<id>/wrangleToPython`, but that endpoint is **deprecated (R9.7)**,
Enterprise-only, **CSV-only**, has **no multi-dataset** support, and sits behind an
experimental flag — so it's used only where it's available and clearly helps, never as the
baseline. **Either way the translator reshapes** into **one self-contained `<flow>.sql`** with
**one CTE per step**, original Wrangle quoted in an inline comment, a file header, and **no
hard-coded values** (dates/params become `CURRENT_DATE()`, `DECLARE`, or query parameters) —
because native output is machine-spew and our value is making it readable and correct. It
proactively applies the five corruption fixes (below).

### Step 3 — Compile & dry-run
A BigQuery dry-run estimates bytes/cost and catches syntax issues before anything runs for
real. If an optional `.sqlx` Dataform wrapper exists, `dataform compile` also catches
structural errors.

### Step 4 — Parity audit (the self-audit)
`@parity-auditor` runs the new model into the **disposable staging dataset**
(`dataprep_migration_staging`) so the legacy table is never touched. It first **freezes the
input** — pinning the source via BigQuery time-travel / a snapshot so both engines see
identical data, otherwise live-source drift looks like a translation bug — then runs a
**4-tier diff**, escalating only as needed:

1. **Schema** — column names + types; renames, drops, type changes
2. **Row count** — totals match (catches filter/join/dedupe divergence)
3. **MD5 row-hash** — hash every row, compare the multisets (efficient deep check at scale)
4. **Cell-level scan** — on any hash mismatch, the exact `(key, column)` coordinates that differ

Legitimate diffs (tz-naive temporals, ordering) are normalized first. Bar is **exact match** in
**Strict Parity** mode — the new table must reproduce legacy *exactly, including its bugs* (e.g.
uncleaned keys); a cleaned "Clean Promotion" version is a separate, documented post-pass. Most
cell-level diffs trace to the five corruption risks below.

### Step 5 — Governance review
`@governance` reviews the finished flow against a checklist and emits a governance report:
**no hard-coded values**, header + inline comments per CTE, a single self-contained `.sql`
file, strict parity green, `validation.sql` + `EXPLANATION.md` present, correct naming, and
read-only/staging discipline. The team owns the migration — Gemini assists, humans validate.

### Step 6 — Report & deliverables
Per flow, `flows/<plan>/<flow>/` gets a `parity.md` (audit evidence), an `EXPLANATION.md`
(plain-English: what it does / why / how to maintain / parity result), and a `validation.sql`
the user runs themselves to compare new vs legacy. On failure the parity report points at the
recipe step whose translation diverged, so the fix is targeted, not a rewrite.

### Signoff — Productionized (human-only)
Promotion to **Productionized requires `/dp:signoff`**: the user attests they independently
reviewed and validated the flow. New and legacy run **side-by-side over a validation window**
(the *Parallel runs* status) before cutover. Legacy is untouched throughout; once it is
retired, any temporary reconciliation is removed.

## 5b. Status lifecycle (gated)

Every flow moves through five stages, tracked against the total inventory in
`status/migration_status.csv` (+ Excel), updated as flows progress:

**Not started → In process → Validating → Parallel runs → Productionized**

- **Status changes are gated.** Gemini asks the user to confirm before advancing a flow.
- **Productionized requires `/dp:signoff`** — a human attestation. Gemini cannot self-promote.

### The five corruption fixes (why migrated output silently disagrees)
Dataprep's engine and standard SQL/Python runtimes differ in five ways that quietly corrupt
data. The translator handles all five up front; they're also the first thing to check on a
parity mismatch:

- **Temporal string drift** — Dataprep parses dates as timezone-naive strings. Moving them to
  a TZ-aware system shifts dates. Keep them tz-naive (`TimestampNTZType` / naive datetime).
- **Decimal precision truncation** — Alteryx `FixedDecimal` allows up to 50 digits; BigQuery
  and Spark cap at **38**. Scale to ≤38 or cast to string, or you get runtime errors / silent loss.
- **Null propagation** — Wrangle treats null == empty string; SQL-92 does not, so `concat(x,
  NULL)` → NULL and rows vanish / aggregates skew. `coalesce`/`nullif`/`fillna` before concat/join.
- **Date midnight** — legacy formats dates `yyyy-MM-dd`; BigQuery `DATETIME` appends `00:00:00`,
  so a direct cast of a timestamp mismatches. Wrap in `datetime_trunc(safe_cast(x as DATETIME), DAY)`.
- **Trailing newlines** in quoted GCS fields — unescaped `\n` is read literally and breaks joins.
  Strict parity: join the raw value (reproduce legacy). Clean: `trim(regexp_replace(col, '^"|"$', ''))`.

## 6. What the output looks like

Readability is requirement #1. The transform dictionary forces a consistent shape so a
reviewer can line up CTE N against recipe step N. **Hard rules:** no hard-coded values
(dates/params → `DECLARE` / `CURRENT_DATE()` / query params), a file header, and an inline
comment on every CTE.

### Primary SQL output (`flows/<plan>/<flow>/cust_clean.sql`)

```sql
-- Migrated from Dataprep flow "Customer Cleanup" (flow_id 4821). 7 recipe steps below.
-- Self-contained: run as-is in the BigQuery console. Writes to staging; legacy untouched.
DECLARE run_date DATE DEFAULT CURRENT_DATE();      -- no hard-coded dates

CREATE OR REPLACE TABLE dataprep_migration_staging.cust_clean AS
with src as (                              -- recipe: import dataset `raw.customers`
  select customer_id, name, email, signup_dt, region from raw.customers
),
step1_trim_email as (                      -- Wrangle: set email: trim(email)
  select * replace (trim(email) as email) from src
),
step2_drop_nulls as (                      -- Wrangle: filter: ISMISSING(customer_id) -> delete
  select * from step1_trim_email where customer_id is not null
)
select * from step2_drop_nulls;
```

For GCS-CSV sources the same file adds the Create-Execute-Clean phases: mount `EXT_` external
tables (with `allow_quoted_newlines = true`) at the top, build the `STG_` CTE graph, then
`DROP EXTERNAL TABLE` for each external at the bottom. An optional `<flow>.sqlx` Dataform
wrapper carries the same CTE graph plus `config { … }` when you want scheduled orchestration.

### Validation (`flows/<plan>/<flow>/validation.sql`) — the user runs this

```sql
-- Compare the migrated table against the legacy Dataprep output. Run yourself; expect 0 rows.
select 'new-not-legacy' as side, * from dataprep_migration_staging.cust_clean
except distinct select 'new-not-legacy', * from legacy.cust_clean
union all
select 'legacy-not-new', * from legacy.cust_clean
except distinct select 'legacy-not-new', * from dataprep_migration_staging.cust_clean;
```

Every step is traceable to its Wrangle origin. `EXPLANATION.md` accompanies each flow in
plain English (what it does / why / how to maintain / parity result).

## 7. How to use it

### One-time
1. Have Gemini CLI installed. (If the global starter kit is installed too, it applies on
   top — nothing to configure.)
2. From this folder, confirm the toolkit loads: in Gemini CLI run `/info` (lists the
   `/dp:migrate` command and the agents) — or just check `.gemini/` exists here.
3. Set your Dataform project / BigQuery connection (see *Setup* below).

### Per flow (the golden path)
1. Export the flow package from Dataprep (`GET /v4/flows/{id}/package`, **or** the UI
   "Export Flow" button — identical ZIP, no API needed) → unzip into `flows/<plan>/<flow>/recipe/`.
2. Run `/dp:start` to pick the next flow, then `/dp:migrate <flow>`. **One flow at a time** — finish
   it end-to-end (and commit) before the next; bulk migration is refused.
3. Read `parity.md` and run `validation.sql` yourself. Green → confirm the status change. Red →
   it tells you which step diverged.
4. When you're satisfied, run **`/dp:signoff <flow>`** to attest you validated it → status
   moves to **Productionized**.

### Bulk discovery (start of the project)
Export all flow packages into `flows/` and ask `@flow-inventory` to profile the whole set →
ranked backlog + dependency graph in `status/`. This read-only discovery is the **only**
bulk-allowed step;
everything after it is one flow at a time, in dependency order (upstream flows first). The
default engine is the transform dictionary, so no Dataprep admin toggle is required — the
optional `wrangleToPython` accelerator (deprecated, Enterprise-only, CSV-only) is used only
if it happens to be available.

## 7b. Distribution — how this package gets shipped

Same files, two modes, matched to the rollout. This package is **fully self-contained** and
does **not** require the rest of any starter kit — recipients get only this.

- **Central team (now): run it as a project folder.** Gemini CLI auto-loads this folder's
  `GEMINI.md`, `.gemini/agents/`, `.gemini/skills/`, and `.gemini/commands/` when you run the
  CLI from here. Zero install. Iterate fast, version-controlled. (Requires a 2026-era CLI:
  skills ≥ v0.24, subagents ≥ v0.38.1.)
- **Lines of business (handoff): package as a Gemini CLI Extension.** Convert this folder to
  an extension — move `.gemini/{agents,skills,commands}` to the extension root and add a
  `gemini-extension.json` manifest (`GEMINI.md` already at root). Then LOB users install with
  one command: `gemini extensions install <git-url>`. It's global in every project,
  **namespaced** (the command may appear as `/<ext>:migrate`) so it can't collide with their
  own setup, auto-updatable, and uninstallable — and it carries none of your other skills.
  *Caveat:* subagents-inside-extensions is currently marked **"preview"** by Google; validate
  on the target CLI version before broad rollout.
- **Do NOT** copy these files into a recipient's global `~/.gemini/` — it pollutes their config,
  has no clean uninstall, and would mix with other tooling. The two modes above cover every case.

## 8. Setup

- **BigQuery access — gcloud not required.** Use the Python `google-cloud-bigquery` client with
  browser OAuth, or the BigQuery console / Dataform UI. Production stays read-only (SELECT-only).
- **Staging dataset**: all writes go to one disposable dataset, `dataprep_migration_staging`,
  created with a default table expiration so it self-cleans; a write-guard refuses any write
  outside it, and the dataset is deleted at teardown. See `references/dataform-conventions.md`.
- **Python**: `pip install bigframes pandas db-dtypes`. See `references/python-lane.md`.
- **Legacy tables**: each flow's `validation.sql` references the legacy Dataprep output table
  so the user can diff against it.

## 9. Conventions

- **Naming**: file/table name = flow's output table name, snake_case. All migrated output lands
  in the staging dataset `dataprep_migration_staging`.
- **One folder per flow** under `flows/<plan>/<flow>/`, created by Gemini one at a time from
  catalog metadata (canonical names, never pre-created or hand-named).
- **No hard-coded values** — dates/params become `DECLARE` / `CURRENT_DATE()` / query params.
- **One CTE per recipe step**, original Wrangle quoted in an inline comment, plus a file
  header. No un-commented logic.
- **File discipline** (all inside `flows/<plan>/<flow>/`): primary `<flow>.sql`; optional
  `<flow>.sqlx`; `validation.sql`; `EXPLANATION.md`; `parity.md`; recipe input in `recipe/`
  (read-only, gitignored — never edit). Plan map → `flows/<plan>/README.md`. Cross-flow
  status tracking → `status/`.
- **Legacy is never modified.** All new output goes to the staging dataset until cutover.

## 10. Build status

Scaffolded and documented. The recipe-dependent assets are drafted from known Wrangle
semantics and **harden against real exported recipes during the pilot** — by design, the
toolkit and the pilot are built together:

- [ ] `references/wrangle-to-sql.md` — transform dictionary → SQL (draft; validate on real recipes)
- [ ] `references/wrangle-to-python.md` — transform dictionary → Python (draft)
- [ ] `references/recipe-anatomy.md` — how to read exported recipe JSON (needs a real sample)
- [ ] `references/dataform-conventions.md`, `references/python-lane.md`, `references/parity-harness.md`
- [ ] `@flow-inventory`, `@recipe-translator`, `@parity-auditor`, `@governance` — drafted; tune on pilot
- [ ] `/dp:start`, `/dp:migrate`, `/dp:signoff` commands — drafted; tune on pilot

**Next concrete step:** get 2–3 real exported recipe JSONs into `flows/<plan>/<flow>/recipe/`
so the transform dictionary and the inventory classifier can be validated against reality.

## 11. FAQ / gotchas

- **Why not just keep the SQL Dataprep already generates in pushdown mode?** We can — for
  pushdown flows that's the fast path. The dictionary still re-shapes it into commented,
  CTE-per-step form so it's maintainable, not machine-spew.
- **What about flows that feed other flows?** The inventory builds the dependency graph and
  migrates upstream flows first; an optional `.sqlx` wrapper expresses deps as `ref()` for
  scheduled runs.
- **Do we migrate Plans, or just flows?** Both. A Dataprep **Plan** is an orchestration unit
  (run order + schedule). Its flows are migrated one at a time into `flows/<plan>/`, and the
  schedule is preserved via an optional Dataform tag-group / Cloud Composer DAG. The
  `flows/<plan>/README.md` and per-flow `EXPLANATION.md` document the mapping.
- **Where does the documentation come from?** It's generated from inventory metadata so it can't
  drift: this estate runbook, a per-Plan README, the per-flow `EXPLANATION.md`, in-code header +
  per-CTE comments, and the **status tracker** (`status/migration_status.csv` + `.xlsx`) — a plain
  file you open directly, updated as flows progress.
- **A flow's logic is genuinely ambiguous from the recipe — now what?** The translator
  flags it rather than guessing; the parity audit is the backstop that catches a wrong guess.
- **Does choosing Python weaken the audit?** No. Parity compares two BigQuery tables and is
  identical regardless of how the new table was produced.
