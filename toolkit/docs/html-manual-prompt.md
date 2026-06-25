# Prompt to give Claude (in chat) to build the HTML manual

Paste everything in the code block into a fresh Claude.ai chat. It produces a single,
self-contained, good-looking HTML manual for this toolkit — no external files, opens by
double-click.

---

```
Build me a single, self-contained, polished HTML manual ("operator's guide") for an internal
tool called the Dataprep → BigQuery Migration Kit. I'll open the .html file by double-clicking
it, so it MUST be fully self-contained.

HARD REQUIREMENTS
- ONE .html file. All CSS and JS inline. NO external fetches, NO loading any .json/.csv, NO CDN
  dependency required to render (if you use a web font, include a system-font fallback so it
  looks right offline). Everything needed is embedded in the file.
- It must look great and read like a real manual: a sticky left sidebar with anchor navigation
  to each section, smooth scroll, a search/filter box that hides non-matching sections is a plus,
  collapsible subsections, and a clean modern technical aesthetic (generous whitespace, one
  accent color + a couple of supporting colors, rounded cards, subtle shadows, monospace for
  code/paths). Responsive down to mobile. Light theme; a dark-mode toggle is a nice bonus.
- Use inline SVG or styled HTML/CSS for the diagrams (pipeline flow, status lifecycle) — no image
  files. Use colored "pills"/badges for statuses and tags. Use cards for commands/agents/skills.
- Tasteful only — this is a professional internal tool, not a marketing splash.

AUDIENCE: data engineers/analysts who will operate the toolkit, plus leads who want to understand
how it works and why it's trustworthy.

BUILD THESE SECTIONS (use this content; it's accurate — make it skimmable and visual):

1) HERO / OVERVIEW
   - Title: "Dataprep → BigQuery Migration Kit". Tagline: "AI-assisted, verifiable migration of
     Dataprep (Trifacta) flows into maintainable BigQuery SQL — owned by your team, not the tool."
   - The core insight (call this out prominently): a Dataprep flow is a "recipe" of steps written
     in Wrangle, a finite declarative DSL. Because the vocabulary is finite, migration is
     TRANSPILATION (apply a reviewed mapping), not a from-scratch rewrite. That's why output is
     consistent and trustworthy.
   - 3 quick stats/《pills》: "1 flow at a time", "Exact-match parity", "Production never touched".

2) HOW IT WORKS — THE PER-FLOW PIPELINE (make this a horizontal flow diagram)
   Extract → Inventory → Translate → Compile/Dry-run → Parity audit → Document → Sign-off.
   Short blurb per stage:
   - Extract: export a flow package (ZIP of flow.json + recipes/ + inputs/ + outputs/) via the
     Dataprep API (GET /v4/flows/{id}/package) or the UI "Export Flow" button (identical ZIP).
   - Inventory: parse the package → backlog, dependency graph, complexity, recommended target.
   - Translate: transpile each Wrangle step → one commented SQL block (a CTE).
   - Compile/Dry-run: catch structure/syntax/cost before running.
   - Parity audit: run into a disposable staging dataset and diff vs the legacy table (below).
   - Document: write the explanation + a user-runnable validation query.
   - Sign-off: a human attests they independently validated it before it goes Productionized.

3) STATUS LIFECYCLE (a colored horizontal stepper)
   Not started → In process → Validating → Parallel runs → Productionized.
   Note: status lives in status/migration_status.csv (+ an Excel view), updated as flows progress;
   status changes are GATED — Gemini asks the user to confirm before advancing; "Productionized"
   requires the sign-off attestation.

4) COMMANDS (cards)
   - /dp:start — orient & resume: reads the status tracker, does first-time setup (API-optional),
     and helps you pick ONE flow to work on; creates that flow's folder + git branch.
   - /dp:migrate <flow> — the golden path for ONE flow: inventory → transpile → compile/dry-run →
     parity → document. Outputs land in flows/<plan>/<flow>/.
   - /dp:signoff <flow> — you attest you independently reviewed AND validated it; status advances
     to Productionized, recording who + when. No rubber-stamping.

5) AGENTS (cards; note "read-only" where it applies)
   - @flow-inventory (read-only) — flow package → backlog, dependency DAG, complexity, target, and
     a status entry.
   - @recipe-translator — recipe → ONE commented, self-contained BigQuery SQL file (one CTE per
     Wrangle step, original step quoted); also writes validation.sql + EXPLANATION.md. No hard-coded
     values; applies the three corruption fixes.
   - @parity-auditor (read-only on legacy) — freezes the input, runs into staging, 4-tier diff.
   - @governance — runs a readiness checklist (no hardcoding, comments present, single self-contained
     file, parity green, validation.sql + EXPLANATION.md present, naming) → a governance report; gates sign-off.

6) THE SKILL & ITS REFERENCES (a tidy list/grid)
   Skill: "dataprep-migration" — the method + a transform dictionary. Reference files:
   wrangle-to-sql, wrangle-to-python, recipe-anatomy, dataform-conventions, python-lane,
   parity-harness, dataprep-api, windows-onedrive, output-standards, governance.
   One-line each on what it covers.

7) OUTPUT STANDARDS (why the SQL is trustworthy & maintainable)
   - SQL-first: ONE self-contained, console-runnable .sql per flow using a "Create-Execute-Clean"
     pattern: mount GCS CSVs as external tables (EXT_*) → transform with a CTE graph → CREATE the
     staging table (STG_*) → DROP the external tables so the schema stays pristine. (Dataform .sqlx
     wrapper is optional, for orchestration.)
   - NO hard-coded values: load/run dates and params become DECLARE vars / CURRENT_DATE() / query
     parameters — required for automation.
   - Heavy commenting: a header block (what / why / when / source / owner / parity result) + an
     inline comment on every CTE.
   - Every flow also ships validation.sql (a query YOU run to compare new vs legacy yourself) and
     EXPLANATION.md (plain-English walkthrough) — so the team validates independently and owns it.

8) THE VERIFICATION ENGINE (this is the trust core — give it weight)
   - Freeze the input: snapshot the source with BigQuery time-travel so the migrated code and the
     legacy Dataprep run see IDENTICAL input (kills false failures from data drift).
   - 4-tier diff, escalating: (1) schema → (2) row count → (3) MD5 row-hash (compare row multisets)
     → (4) cell-level (the exact key + column that differ).
   - Normalize known-legitimate differences first (column order, float rounding, row order, timezone,
     surrogate keys). Bar is exact match.
   - The three silent-corruption fixes, always applied: (a) Temporal — Dataprep dates are
     timezone-naive strings; keep them tz-naive to avoid date-shift. (b) Decimal — cap precision at
     38 (Alteryx allows 50; BigQuery caps at 38). (c) Null propagation — coalesce before string
     concatenation (Wrangle treats null == empty string; SQL-92 doesn't).

9) SAFETY & ACCESS MODEL (a reassuring, scannable panel)
   - Dataprep is READ-ONLY: the toolkit only GETs (list + export). It never creates, edits, deletes,
     or runs anything in Dataprep. Migration is one-directional.
   - Production (BigQuery) is read-only: SELECT-only on source/legacy; never DDL/DML.
   - All writes go to ONE disposable staging dataset (dataprep_migration_staging) with a default
     table expiration so it self-cleans; a write-guard refuses any non-staging write.
   - gcloud not required: use the Python BigQuery client with browser OAuth, or the BigQuery console
     / Dataform UI.
   - API-optional: business units without API access use the UI export; everything downstream is identical.

10) FOLDER STRUCTURE (a styled file-tree)
   flows/<plan>/<flow>/  ->  <flow>.sql (primary), <flow>.sqlx (optional), validation.sql,
     EXPLANATION.md, parity.md, governance.md, recipe/ (read-only input, gitignored)
   status/  ->  migration_status.csv (source of truth), migration_status.xlsx, backlog.md
   scripts/  ->  discovery (01_sweep, 02_download_unzip, 03_job_stats, 04_compile_catalog)
   .gemini/  ->  agents, the skill, commands
   docs/  ->  guides & this manual ;  plus GEMINI.md / README / SETUP / GUIDE / CONTRIBUTING / MAINTAINING at root.
   Note: ONE folder per flow — everything about a flow lives together. Folders are created by Gemini
   from canonical names, one at a time — never pre-created or hand-named.

11) DISCOVERY SCRIPTS (run order)
   01_sweep.py (list all flows/plans; limit=250 + flowsFilter/plansFilter=all so nothing truncates)
   → 02_download_unzip.py (export packages → flows/<plan>/<flow>/recipe/, Windows-safe names)
   → 03_job_stats.py (job history → runs, durations, owners) → 04_compile_catalog.py (build the
   status tracker; preserves any status/sign-off you've already set). READ-ONLY.

12) GOVERNANCE & OWNERSHIP (close on this — it's the philosophy)
   The team owns the migration; Gemini assists. Nothing is "Productionized" on Gemini's say-so —
   a human runs the validation query, reviews the SQL, and signs off. @governance checks quality;
   /dp:signoff records the human attestation. The toolkit also keeps improving in place via a
   documented hardening loop (capture each new finding back into the references).

FOOTER: "Generated manual — the repo is the source of truth." Leave a small [version/date] placeholder.

Deliver the single .html file. Keep the content faithful to the above; make it beautiful and easy
to navigate.
```
