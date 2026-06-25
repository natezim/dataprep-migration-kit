# Handoff — Dataprep → BigQuery Migration Kit

Everything you need to take this over and keep building it in Gemini. The toolkit is in
[`toolkit/`](toolkit/); deep docs are `toolkit/GUIDE.md` (how it works) and `toolkit/MAINTAINING.md`
(how to keep improving it). This doc is the orientation + the *why* + the current status.

## 1. What we built

A repeatable, AI-assisted toolkit that migrates ~100 Dataprep (Trifacta) flows — organized in
Plans — into maintainable BigQuery SQL, **one flow at a time**, each one **verified against the
live Dataprep output** before it's trusted, and **never touching Dataprep or production**.

**The core insight:** a Dataprep flow is a *recipe* of steps written in **Wrangle**, a finite
declarative DSL. Because the vocabulary is finite, migration is **transpilation** (apply a reviewed
mapping), not a from-scratch rewrite. That's what makes the output consistent and trustworthy.

## 2. What's in the box

- **Commands** (`toolkit/.gemini/commands/dp/`): `/dp:start` (orient + pick one flow),
  `/dp:migrate <flow>` (the golden path for one flow), `/dp:signoff <flow>` (human attestation →
  Productionized).
- **Agents** (`toolkit/.gemini/agents/`): `@flow-inventory` (read-only: package → backlog/DAG/target),
  `@recipe-translator` (recipe → one commented SQL file + `validation.sql` + `EXPLANATION.md`),
  `@parity-auditor` (read-only on legacy: frozen-input 4-tier diff), `@governance` (readiness checklist).
- **Skill** (`toolkit/.gemini/skills/dataprep-migration/`): the method + a transform dictionary,
  with reference files (wrangle-to-sql, wrangle-to-python, recipe-anatomy, dataform-conventions,
  python-lane, parity-harness, dataprep-api, windows-onedrive, output-standards, governance).
- **Discovery scripts** (`toolkit/scripts/`): READ-ONLY sweep → export → job stats → status tracker.
- **Status tracker** (`toolkit/status/`): `migration_status.csv` (+ Excel) — the live source of truth.
- **Per-flow output** (`toolkit/flows/<plan>/<flow>/`): `<flow>.sql`, optional `<flow>.sqlx`,
  `validation.sql`, `EXPLANATION.md`, `parity.md`, `governance.md`, `recipe/` (read-only input).
- **A visual manual**: `toolkit/docs/operators-guide.html` (self-contained, opens in a browser).

## 3. How it works (condensed — full detail in `toolkit/GUIDE.md`)

Per flow: **Extract** (API or UI export — identical ZIP) → **Inventory** → **Translate**
(transpile each Wrangle step to one commented CTE) → **Compile/dry-run** → **Parity audit** (run
into staging, diff vs legacy) → **Document** → **Sign-off**.

**Verification engine:** freeze the input (BigQuery time-travel) so both engines see identical
data → 4-tier diff (schema → row count → MD5 row-hash → cell-level) → normalize legitimate diffs →
**exact match**. Three corruption fixes are always applied: timezone-naive temporals, decimal ≤ 38,
coalesce-before-concat.

## 4. Why it's built this way (don't undo these without good reason)

- **Transpile-first, native code-gen demoted.** We tested Dataprep's `wrangleToPython` — it's
  deprecated (R9.7), Enterprise-only, CSV-only, no multi-dataset. So the owned transform dictionary
  is the engine; native gen is a rare accelerator.
- **SQL-first, one self-contained file.** Easiest to read, run in the console, and own. Dataform
  `.sqlx` is optional (orchestration only).
- **Frozen-input parity.** Without it, live-source drift looks like a translation bug and destroys
  trust in the check. This was a deliberate fix.
- **One flow at a time + human sign-off.** Bulk migration produces an unreviewable mess, and the
  team is responsible for the result regardless of what Gemini did — so nothing is "Productionized"
  without a human running the validation query and attesting.
- **Read-only Dataprep/prod + disposable staging + write-guard.** Access is likely user-OAuth (no
  locked-down service account), so safety is enforced by read-only *operations* + a write-guard,
  not just IAM.
- **API-optional + gcloud-free.** Business units may have neither an API token nor gcloud; the UI
  export path and browser-OAuth/console path are first-class so everyone can use it.
- **Generated, drift-proof docs + the hardening loop.** The `references/` are the brain; every new
  finding is captured back so the toolkit keeps improving in place.

## 5. Current status

- ✅ **Built & on GitHub**, fully restructured (toolkit/ + this handoff root).
- ⚠️ **Discovery scripts** were reconstructed from real production findings (87 flows / 14 plans /
  3,000 runs) — **smoke-test against your Dataprep version** first; JSON shapes can vary
  (`toolkit/scripts/README.md` notes which).
- ⚠️ **Transform dictionary** is drafted from known Wrangle semantics + the first real findings —
  it **hardens as you migrate real flows**. Expect to iterate on the first few.
- ⬜ **Dataform `workflow_settings.yaml`** needs your real project/dataset (only if you use `.sqlx`).
- ⬜ **First real `/dp:migrate` end-to-end** not yet run against a live flow.

## 6. How to continue (in Gemini, on any machine)

1. Open Gemini CLI at this repo root → it loads `GEMINI.md` (the dev context).
2. To make a change, find the right file per the table in `GEMINI.md` / `toolkit/MAINTAINING.md`,
   make a small focused edit, keep the **non-negotiables** (see `GEMINI.md` §Non-negotiables), commit.
3. To run an actual migration, `cd toolkit/` and use `/dp:start` → `/dp:migrate` → `/dp:signoff`.
4. When a real flow reveals a gap, capture it back into the right `references/` file — that's the
   loop in `toolkit/MAINTAINING.md`.

A paste-able kickoff prompt is in [`PROMPT.md`](PROMPT.md).
