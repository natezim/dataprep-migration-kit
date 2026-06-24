# GEMINI.md — Dataprep Migration project rules

Project-scoped rules for migrating Dataprep (Trifacta) flows into BigQuery SQL or Python.
Auto-loaded when Gemini CLI runs from this folder. The global starter-kit `~/.gemini/GEMINI.md`
(if installed) applies on top — this file does not replace it, only adds migration rules.

## Mission

Translate exported Dataprep recipe JSON into maintainable, commented BigQuery assets, and
prove each one matches the legacy Dataprep output before promoting it. Repeatable golden
path; output readable enough for lines of business to maintain.

## Work discipline — ONE flow at a time (hard rule)

This is the most important rule. The migration is sequential, not bulk.

- **Migrate exactly ONE flow, end-to-end, before starting another.** End-to-end =
  translate → compile/dry-run → parity-verify → document → commit. Only then pick the next.
- **Never bulk-migrate.** If asked to "migrate everything" / "do all the flows," refuse the
  bulk action: explain why, then migrate the FIRST one only and report back.
- **The only bulk-allowed step is discovery** (`@flow-inventory` across `context/`) — it is
  read-only and just builds the backlog + catalog. Translation and promotion are one-at-a-time.
- **Finish in-progress work first.** On resume, complete any flow marked `In progress` in
  `docs/catalog.json` before starting a new one.
- Work a **Plan** by planning it out, then migrating its flows one at a time in dependency order.
- Keep the workspace clean: scratch goes in `output/temp/`; nothing at the folder root; every
  new file has a home per File discipline below.

## Targets — SQL-first (Python is a rare exception)

- **BigQuery Standard SQL is the PRIMARY lane.** Every flow targets SQL (Dataform) unless SQL
  literally cannot express the logic.
- **Dual deliverable per flow (required):** (a) a Dataform model
  `definitions/<plan>/<flow>/<flow>.sqlx` (`config { type: "operations", hasOutput: true, ... }`),
  and (b) a standalone copy-paste `.sql` in `output/queries/<table>.sql` (config stripped,
  run-instructions header) that runs as-is in the BigQuery console.
- **Python is a RARE exception** (`python/<plan>/<flow>/`) — only when SQL can't express the logic
  (heavy multi-step regex, row-wise/iterative logic, fuzzy match, ML/Vertex). Not first-class; justify it.

## Translation rules

- **Transpile-first.** Wrangle is a finite declarative DSL, so migration is transpilation:
  apply the reviewed **transform dictionary** (one known SQL/Python pattern per step) plus
  **pushdown-SQL reuse** for BigQuery-source flows. That dictionary is the engine.
- **Native gen is a rare optional accelerator, not the default.** `POST
  /v4/outputObjects/<id>/wrangleToPython` is **deprecated (R9.7)**, Enterprise-only, CSV-only,
  no multi-dataset, behind an experimental flag. Use it only if it's available and clearly
  helps; otherwise transpile. Either way, always reshape into our commented form.
- **One CTE per legacy recipe node**, commented with its original recipe ID. **No `SELECT *` in
  joins** — coalesce/cast/alias columns explicitly.
- **Create-Execute-Clean lifecycle** for GCS-CSV sources (single self-contained script):
  Phase 1 `CREATE OR REPLACE EXTERNAL TABLE EXT_*` on the GCS CSV (OPTIONS incl.
  **`allow_quoted_newlines = true`**); Phase 2 `CREATE OR REPLACE TABLE STG_* AS <CTE graph>`;
  Phase 3 `DROP EXTERNAL TABLE IF EXISTS` for every external at the bottom. BQ-native sources
  skip the external phases and `ref()` directly. (See `references/dataform-conventions.md`.)
- Never invent logic. If a step is ambiguous, flag it in the output and the report — do not guess.
- **Defend against the five silent-corruption risks** (top parity-failure sources; see
  `references/wrangle-to-python.md`):
  1. **Temporal** — Dataprep dates are tz-naive strings; keep them tz-naive to avoid date-shift.
  2. **Decimal** — cap precision at 38 digits (Alteryx allows 50; BQ/Spark cap at 38) or cast to string.
  3. **Null propagation** — `coalesce`/`nullif`/`fillna` before any string concat or join.
  4. **Date midnight** — `datetime_trunc(safe_cast(x as DATETIME), DAY)` to match Dataprep's
     `yyyy-MM-dd` (BigQuery otherwise appends `00:00:00`).
  5. **Trailing newlines** in quoted GCS fields — reproduce raw in strict parity; clean with
     `trim(regexp_replace(col, '^"|"$', ''))` for promotion.

## Parity audit — exact match, non-negotiable

- **Frozen input.** Pin the source with BigQuery time-travel / a snapshot so both engines see
  identical data; otherwise drift in the live source masquerades as a translation bug.
- **4-tier diff**, escalating only as needed: (1) **schema** → (2) **row count** → (3) **MD5
  row-hash** (compare row multisets) → (4) **cell-level** (the exact `(key, column)` coords).
- Normalize legitimate diffs (e.g. tz-naive temporals, ordering); bar is **exact match** —
  any undocumented difference fails the flow.
- **Two modes.** Audit in **Strict Parity** mode: reproduce the legacy output EXACTLY, *including
  its bugs* (e.g. uncleaned keys with trailing newlines, failed joins) — join on raw keys so the
  new table is bit-for-bit identical to legacy. **Clean Promotion** is a separate, documented
  post-pass (fix the legacy bugs) done only AFTER strict parity passes; it is never audited against legacy.
- New output is written only to the **disposable staging dataset** (see Safety); legacy tables
  are NEVER modified. New and legacy run side-by-side over a validation window before cutover.
- Parity is target-agnostic — same check whether SQL or Python produced the table.

## File discipline — folders mirror Plan → flow

Per-flow folders are created by Gemini one at a time, with canonical names from catalog
metadata — never pre-created or hand-named.

| Type | Folder |
|---|---|
| Exported recipe input (read-only, gitignored) | `context/<plan>/<flow>/` |
| SQL Dataform model (`.sqlx`) | `definitions/<plan>/<flow>/` |
| SQL console script (`.sql`, copy-paste) | `output/queries/<table>.sql` |
| Python flows (`.py`, rare) | `python/<plan>/<flow>/` |
| Parity evidence | `output/parity/<plan>/<flow>.md` |
| Human Plan map | `plans/<plan>/README.md` |
| Catalog dashboard | `docs/catalog.json` + `docs/catalog.html` |

- `context/` is READ-ONLY. Copy out to work; never edit recipe inputs.
- Never write migrated logic at the folder root. Scratch → `output/temp/`.
- **Sanitize folder names: ≤60 chars, `[a-zA-Z0-9_.-]` only, no flow-ID suffixes** — Windows
  `MAX_PATH` (260) truncates deep trees and silently fails extraction. See `references/windows-onedrive.md`.

## Safety & access

- **Dataprep is read-only — export only. The toolkit NEVER changes anything in Dataprep.**
  Only reads are allowed: `GET /v4/flows`, `GET /v4/plans`, `GET /v4/flows/{id}/package`,
  `GET /v4/jobGroups`. NEVER call any create/edit/delete/run endpoint (`replaceDataset`,
  `POST /v4/outputObjects`, job triggers). Migration is one-directional: logic flows OUT of
  Dataprep; nothing alters a flow, recipe, dataset, output, or schedule.
- **Discovery query params (or the catalog silently truncates):** append `limit=250` to every
  list call, and `flowsFilter=all` / `plansFilter=all` to see team-shared + ex-employee flows
  (default scope is only the token owner's). Map plan runs via the embedded `latestPlanSnapshotRun`
  on each plan — NOT `/v4/planSnapshotRuns`. See `references/dataprep-api.md`.
- **Production (BigQuery) is read-only.** SELECT-only against source/legacy tables — never DDL/DML.
- **All writes go to one disposable staging dataset, `dataprep_migration_staging`**, created
  with a default table expiration so it self-cleans, and deleted at teardown. A **write-guard
  refuses any write whose destination isn't that dataset.**
- **gcloud is NOT required.** Access via the Python `google-cloud-bigquery` client with browser
  OAuth, or via the BigQuery console / Dataform UI.
- **API-optional.** The Dataprep API (`GET /v4/flows/{id}/package`, `GET /v4/flows`) is the fast
  path, but the UI "Export Flow" button yields the identical ZIP — LOB users with no API access
  are fully supported.
- Reads, dry-runs, compiles → proceed. Running a model into the staging dataset → fine.
  Anything touching a **legacy / production** table, or a write outside the staging dataset
  (CRITICAL) → hard stop, show the full plan, require explicit yes.
- Always BigQuery dry-run before a real run; warn if estimated scan is large.

## Where this lives — git workflow

The project is version-controlled with **git**. This works the same whether or not a remote
(GitHub or GitLab) exists yet — start local, add the remote later with zero rework.

- **No remote yet?** Run `git init` here and commit. You get full history/rollback today, on
  one machine. When a remote is ready: `git remote add origin <url>` and `git push` — the whole
  history goes with it, and CI/Pages (GitHub Pages or GitLab Pages) turn on. Nothing to redo.
- **One flow = one branch = one commit (or MR).** Before migrating a flow, create a branch
  `migrate/<plan>-<flow>`. Do the full end-to-end migration on it. Commit when parity is green.
  This makes every flow individually reviewable and keeps the trunk clean.
- **Do NOT** put the git repo inside a OneDrive/SharePoint-synced folder — syncing the `.git`
  directory corrupts it. Use git for the project; share read-only artifacts (the dashboard,
  reports) via SharePoint/Teams separately.
- Gemini syncs via git: `git pull` to start, `git commit`/`git push` to save. Needs git
  credentials configured once (token or SSH key).
- `.gitignore` already keeps secrets (`.env`), raw exports, and `output/temp/` out of the repo.

## Agents

- `@flow-inventory` — recipe package → backlog + dependency graph + complexity + target pick. Read-only.
- `@recipe-translator` — recipe → commented `.sqlx` or `.py`. Writes to `definitions/` or `python/`.
- `@parity-auditor` — staging run + 4-tier diff (frozen input) → pass/fail report. Read-only against legacy.

## Commands

- `/dp:start` — orient/resume: shows progress, enforces one-flow-at-a-time, helps you pick the next.
- `/dp:migrate <flow>` — the golden path for ONE flow: inventory → translate → verify → document.
