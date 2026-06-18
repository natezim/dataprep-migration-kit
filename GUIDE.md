# Dataprep Migration Kit — Guide

How this toolkit works, and how to use it to migrate Dataprep (Trifacta) flows into
BigQuery SQL or Python — repeatably, with readable output and an automatic audit that
proves each migration matches what Dataprep produced.

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

## 3. Two targets: SQL or Python

Every flow lands in one of two targets, chosen by complexity. **Python is first-class,
not a fallback.**

| Choose… | When the recipe is… | Runtime |
|---|---|---|
| **SQL** (Dataform `.sqlx`) — default | Set-based: filters, joins, aggregations, pivots, dedupe, simple derivations | BigQuery, orchestrated by Dataform |
| **Python** (bigframes / pandas) | Multi-step regex/parsing chains, row-wise or iterative logic, fuzzy matching, ML / Vertex AI steps, external lookups/API enrichment | bigframes (pushes down to BigQuery) or pandas; scheduled via Cloud Run / Composer / Vertex |

A flow can be **hybrid**: SQL for the bulk, one Python step for the hard part, stitched
together in the dependency graph.

**The decision rule lives in two places** and is applied automatically:
`GEMINI.md` (package root) and `.gemini/skills/dataprep-migration/SKILL.md`.

Key property: **the parity audit is target-agnostic.** It compares two BigQuery tables —
it does not care whether SQL or Python produced the new one. So choosing Python costs you
nothing in auditability.

## 4. Why Dataform for the SQL target

- **Dependency graph** — flows that feed other flows become `ref()` calls; Dataform builds
  and runs them in the right order.
- **Assertions = the self-audit, built in** — our parity checks are native Dataform
  assertions, version-controlled in git.
- **Readable & maintainable** — plain `.sqlx` in a repo. An LOB analyst can read it.
- **Google-native and free** — runs inside BigQuery; no extra platform.

## 5. The pipeline — what happens to every flow

This is the repeatable golden path. The `/dp:migrate` command runs all six steps; you can
also run any agent by hand.

```
  context/<plan>/<flow>/
        │
   1. INVENTORY      @flow-inventory  → parse flow package: sources, outputs, every step,
        │                               DAG deps, complexity, TARGET (SQL/Python).
   2. TRANSLATE      @recipe-translator → transpile via the transform dictionary;
        │                               one commented CTE (or Python block) per step
   3. COMPILE        dataform compile + BigQuery dry-run (cost & syntax)
        │
   4. PARITY AUDIT   @parity-auditor  → run into the disposable staging dataset, 4-tier diff
        │                               vs legacy on a frozen input
        │                               (schema → rows → MD5 hash → cell). Exact-match bar.
   5. REPORT         pass/fail report in output/parity/. Fail → shows the diverging step.
        │
   6. PROMOTE        pass → merge to repo, audit-logged. Legacy untouched throughout.
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
logic are the hard minority. Across all flows this produces the ranked **backlog**
(`output/backlog.md`) and the graph. See `references/recipe-anatomy.md` for the package schema.
Discovery is read-only and the **only** bulk-allowed step.

### Step 2 — Translate (transpile-first)
`@recipe-translator` is the workhorse. Because Wrangle is a finite declarative DSL, translation
is **transpilation**: it applies the reviewed **transform dictionary** (one known SQL/Python
pattern per step) and reuses **pushdown SQL** for BigQuery-source flows. That dictionary plus
pushdown reuse is the engine — not a from-scratch rewrite.

**Native gen is a rare optional accelerator, not the default.** Dataprep can emit Python via
`POST /v4/outputObjects/<id>/wrangleToPython`, but that endpoint is **deprecated (R9.7)**,
Enterprise-only, **CSV-only**, has **no multi-dataset** support, and sits behind an
experimental flag — so it's used only where it's available and clearly helps, never as the
baseline. **Either way the translator reshapes** into **one CTE per step (SQL)** or **one
commented block per step (Python)**, original Wrangle quoted, flow deps as `ref()` — because
native output is machine-spew and our value is making it readable and correct. It proactively
applies the three corruption fixes (below).

### Step 3 — Compile & dry-run
`dataform compile` catches structural errors; a BigQuery dry-run estimates bytes/cost and
catches syntax issues before anything runs for real.

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

Legitimate diffs (tz-naive temporals, ordering) are normalized first. Bar is **exact match** —
any undocumented difference fails the flow. Most cell-level diffs trace to the three corruption
risks below.

### Step 5 — Report
A parity report lands in `output/`. On failure it points at the recipe step whose
translation diverged, so the fix is targeted, not a rewrite.

### Step 6 — Promote
Green parity → the `.sqlx` / Python script is merged into the repo and the action is
audit-logged. New and legacy run **side-by-side over a validation window** before cutover.
During the migration window each flow keeps a temporary reconciliation assertion; once legacy
is retired, the assertion is deleted.

### The three corruption fixes (why migrated output silently disagrees)
Dataprep's engine and standard Python/SQL runtimes differ in three ways that quietly corrupt
data. The translator handles all three up front; they're also the first thing to check on a
parity mismatch:

- **Temporal string drift** — Dataprep parses dates as timezone-naive strings. Moving them to
  a TZ-aware system shifts dates. Keep them tz-naive (`TimestampNTZType` in Spark / naive
  datetime in pandas).
- **Decimal precision truncation** — Alteryx `FixedDecimal` allows up to 50 digits; BigQuery
  and Spark cap at **38**. Scale to ≤38 or cast to string, or you get runtime errors / silent loss.
- **Null propagation** — Wrangle treats null == empty string; SQL-92 does not, so `concat(x,
  NULL)` → NULL and rows vanish / aggregates skew. `coalesce`/`fillna` before every string concat.

## 6. What the output looks like

Readability is requirement #1. The transform dictionary forces a consistent shape so a
reviewer can line up output block N against recipe step N.

### SQL output (`definitions/<plan>/<flow>/cust_clean.sqlx`)

```sql
config { type: "table", schema: "dataprep_migration_staging", tags: ["flow:cust_clean", "lob:retail"],
         assertions: { uniqueKey: ["customer_id"], nonNull: ["customer_id", "email"] } }

-- Migrated from Dataprep flow "Customer Cleanup" (flow_id 4821). 7 recipe steps below.
with src as (                              -- recipe: import dataset `raw.customers`
  select customer_id, name, email, signup_dt, region from ${ref("raw_customers")}
),
step1_trim_email as (                      -- Wrangle: set email: trim(email)
  select * replace (trim(email) as email) from src
),
step2_drop_nulls as (                      -- Wrangle: filter: ISMISSING(customer_id) -> delete
  select * from step1_trim_email where customer_id is not null
)
select * from step2_drop_nulls
```

### Python output (`python/<plan>/<flow>/cust_enrich.py`)

```python
"""Migrated from Dataprep flow "Customer Enrich" (flow_id 5102).
Target: Python — recipe uses a multi-step regex parse + fuzzy match (not clean in SQL).
Output: dataprep_migration_staging.cust_enrich   Parity: see output/parity/<plan>/cust_enrich.md
"""
import bigframes.pandas as bpd

df = bpd.read_gbq("raw.customers")                 # recipe: import dataset raw.customers
df["domain"] = df["email"].str.extract(r"@(.+)$")  # Wrangle: extractpatterns email -> domain
# ... one commented block per recipe step ...
df.to_gbq("dataprep_migration_staging.cust_enrich", if_exists="replace")
```

Every step is traceable to its Wrangle origin; every model is tagged by flow and LOB.

## 7. How to use it

### One-time
1. Have Gemini CLI installed. (If the global starter kit is installed too, it applies on
   top — nothing to configure.)
2. From this folder, confirm the toolkit loads: in Gemini CLI run `/info` (lists the
   `/dp:migrate` command and the agents) — or just check `.gemini/` exists here.
3. Set your Dataform project / BigQuery connection (see *Setup* below).

### Per flow (the golden path)
1. Export the flow package from Dataprep (`GET /v4/flows/{id}/package`, **or** the UI
   "Export Flow" button — identical ZIP, no API needed) → unzip into `context/<plan>/<flow>/`.
2. Run `/dp:start` to pick the next flow, then `/dp:migrate <flow>`. **One flow at a time** — finish
   it end-to-end (and commit) before the next; bulk migration is refused.
3. Read the parity report in `output/parity/`. Green → promote. Red → it tells you which step diverged.

### Bulk discovery (start of the project)
Export all flow packages into `context/` and ask `@flow-inventory` to profile the whole set →
ranked backlog + dependency graph. This read-only discovery is the **only** bulk-allowed step;
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
- **Legacy tables**: each parity check declares the legacy Dataprep output table as a
  source so it can diff against it. Declarations live in `definitions/sources/`.

## 9. Conventions

- **Naming**: model name = flow's output table name, snake_case. All parity output lands in the
  staging dataset `dataprep_migration_staging`.
- **Folders mirror Plan → flow**, created by Gemini one at a time from catalog metadata
  (canonical names, never pre-created or hand-named).
- **Tags**: every model tagged `flow:<id>` and `lob:<name>` so you can run/track by flow or business unit.
- **One block per recipe step**, original Wrangle quoted in a comment. No un-commented logic.
- **File discipline**: SQL → `definitions/<plan>/<flow>/`, Python → `python/<plan>/<flow>/`,
  parity evidence → `output/parity/<plan>/<flow>.md`, Plan map → `plans/<plan>/`, dashboard →
  `docs/`, recipe input → `context/<plan>/<flow>/` (read-only, gitignored). Never edit `context/`.
- **Legacy is never modified.** All new output goes to the staging dataset until cutover.

## 10. Build status

Scaffolded and documented. The recipe-dependent assets are drafted from known Wrangle
semantics and **harden against real exported recipes during the pilot** — by design, the
toolkit and the pilot are built together:

- [ ] `references/wrangle-to-sql.md` — transform dictionary → SQL (draft; validate on real recipes)
- [ ] `references/wrangle-to-python.md` — transform dictionary → Python (draft)
- [ ] `references/recipe-anatomy.md` — how to read exported recipe JSON (needs a real sample)
- [ ] `references/dataform-conventions.md`, `references/python-lane.md`, `references/parity-harness.md`
- [ ] `@flow-inventory`, `@recipe-translator`, `@parity-auditor` — drafted; tune on pilot
- [ ] `/dp:migrate` command — drafted; tune on pilot

**Next concrete step:** get 2–3 real exported recipe JSONs into `context/` so the
transform dictionary and the inventory classifier can be validated against reality.

## 11. FAQ / gotchas

- **Why not just keep the SQL Dataprep already generates in pushdown mode?** We can — for
  pushdown flows that's the fast path. The dictionary still re-shapes it into commented,
  CTE-per-step form so it's maintainable, not machine-spew.
- **What about flows that feed other flows?** Handled by `ref()` — the inventory builds the
  dependency graph; Dataform runs them in order.
- **Do we migrate Plans, or just flows?** Both. A Dataprep **Plan** is an orchestration unit
  (run order + schedule), so it's migrated as a **Dataform tag-group + scheduled run** or a
  **Cloud Composer DAG** that preserves that order and schedule — not just its flows in
  isolation. Per-Plan and per-flow READMEs document the mapping.
- **Where does the documentation come from?** It's generated from inventory metadata so it can't
  drift: an estate runbook (README), a per-Plan README, a per-flow README, in-code header +
  per-step comments, and the **catalog dashboard** (`docs/catalog.json` + `docs/catalog.html`).
  Host the dashboard on GitHub Pages or GitLab Pages — CI only publishes; the toolkit
  regenerates `catalog.json`.
- **A flow's logic is genuinely ambiguous from the recipe — now what?** The translator
  flags it rather than guessing; the parity audit is the backstop that catches a wrong guess.
- **Does choosing Python weaken the audit?** No. Parity compares two BigQuery tables and is
  identical regardless of how the new table was produced.
