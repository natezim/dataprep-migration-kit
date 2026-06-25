# Dataprep Migration Kit

Migrate Dataprep (Trifacta) flows off Dataprep into **BigQuery SQL**, using Gemini CLI. Each
flow becomes one self-contained, console-runnable `.sql` file — commented, no hard-coded
values, version-controlled, and **self-auditing**: every migrated table is compared against the
legacy Dataprep output, and a human validates and signs off before it ships.

This is a **standalone toolkit**. It does not modify, and does not require, the Gemini CLI
starter kit (`global/`, `project-template/`). It carries its own `GEMINI.md` + `.gemini/` so
it runs entirely on its own — recipients get only this. If a global starter kit happens to be
installed, its rules apply on top (additive). **Two ways to ship it** (same files): run it as
a project folder now, or package it as a Gemini CLI **Extension** for one-command install when
you hand it to lines of business — see [GUIDE.md](GUIDE.md) §7b.

> **The team owns the migration. Gemini assists; humans validate and sign off.**

> **Setting up to use it today? → [SETUP.md](SETUP.md).** Prereqs, config, first run.
> **Want the visual manual? → [docs/operators-guide.html](docs/operators-guide.html).** Open it in a browser — a self-contained operator's guide.
> **Want to understand how it works? → [GUIDE.md](GUIDE.md).** End to end.
> **Keeping it improving (the hardening loop) → [MAINTAINING.md](MAINTAINING.md).** For the team and for Gemini.

## Quickstart

```powershell
# 1. Export a flow package from Dataprep — API GET /v4/flows/{id}/package, OR the
#    UI "Export Flow" button (identical ZIP; no API access needed). Unzip into:
#    flows/<plan>/<flow>/recipe/

# 2. From the project folder, in Gemini CLI:
/dp:start          # orient/resume — pick the next flow, one at a time
/dp:migrate <flow> # the golden path for that one flow
/dp:signoff <flow> # the human attests they validated it → Productionized
```

`/dp:migrate` runs the full pipeline: inventory → transpile into one self-contained SQL file
→ compile & dry-run → 4-tier parity audit against a frozen input → governance review →
report. You get a commented, hard-code-free SQL file plus a pass/fail parity report and a
`validation.sql` you run yourself. **One flow at a time** — bulk runs are refused; only
read-only discovery is bulk.

## One folder per flow

Everything for a flow lives in **`flows/<plan>/<flow>/`**:

| File | What |
|---|---|
| `<flow>.sql` | **PRIMARY** — one self-contained, console-runnable BigQuery SQL (Create-Execute-Clean: mount GCS CSVs as `EXT_` external tables → `STG_` CTE graph → DROP). Clean, single file, no hard-coded values. |
| `<flow>.sqlx` | OPTIONAL Dataform wrapper — only when you want scheduled orchestration. |
| `validation.sql` | A query **the user runs themselves** to compare new vs legacy and see the result. |
| `EXPLANATION.md` | Plain-English: what it does / why / how to maintain / parity result. |
| `parity.md` | Audit evidence. |
| `recipe/` | The exported recipe (read-only, gitignored). |

Plus `flows/<plan>/README.md` (the Plan map). Cross-flow tracking lives in `status/`.

## Folder map

| Path | What |
|---|---|
| `flows/<plan>/<flow>/` | **Per-flow work** — the SQL, validation, explanation, parity, recipe (above) |
| `flows/<plan>/README.md` | Human-readable Plan map |
| `status/migration_status.csv` + `.xlsx` | Live cross-flow tracker — open directly (no server) |
| `status/backlog.md` | Ranked backlog |
| `scripts/` | Read-only discovery (sweep, download, job stats, compile tracker) |
| `docs/` | Deck / guide artifacts (executive brief, slide prompt) |
| `GEMINI.md` | Project rules + output standards (auto-loaded from project root) |
| `.gemini/` | The toolkit — agents, skill, `/dp:start` + `/dp:migrate` + `/dp:signoff` commands |

## Status lifecycle

Each flow moves through: **Not started → In process → Validating → Parallel runs →
Productionized** (tracked against the total inventory). The live tracker is
`status/migration_status.csv` (+ Excel), updated as flows progress.

- **Status changes are gated** — Gemini asks the user to confirm before advancing a flow.
- **Productionized requires `/dp:signoff`** — the user attests they independently reviewed and
  validated the flow. Gemini cannot self-promote.

## Governance

When a flow is finished, the **`@governance`** agent reviews it against a checklist — no
hard-coded values, header + inline comments, single self-contained file, strict parity green,
`validation.sql` + `EXPLANATION.md` present, correct naming, read-only/staging discipline —
and emits a governance report. Humans validate and sign off; Gemini only assists.

## Output quality (hard rules)

- **No hard-coded values.** Dates and params become variables — `CURRENT_DATE()`, `DECLARE`,
  query parameters.
- **Heavy commenting.** A file header plus an inline comment per CTE tracing to its recipe step.
- **SQL-first, single self-contained file** per flow.
- **Independently validatable** — every flow ships `validation.sql` + `EXPLANATION.md` so the
  team can confirm parity without taking Gemini's word for it.

## Safety

Production and Dataprep stay **read-only** (SELECT-only, never DDL/DML). Every write goes to one
**disposable staging dataset** (`dataprep_migration_staging`) with a default table expiration
that self-cleans and is deleted at teardown; a write-guard refuses non-staging writes. **gcloud
is not required** — use the Python `google-cloud-bigquery` client with browser OAuth, or the
BigQuery console / Dataform UI.

## Version control

Plain **git**, working locally today; add a **GitHub or GitLab** remote later with zero rework.
One flow = one branch (`migrate/<plan>-<flow>`) = one commit. The status tracker is a plain
CSV/Excel you open directly — no hosting needed. Do **not** keep the `.git` repo in a
OneDrive/SharePoint-synced folder.

## Status

Scaffolded. The transform dictionary (`.gemini/skills/dataprep-migration/references/`)
is drafted from known Wrangle semantics and **gets hardened against your real exported
recipes during the pilot.** See [GUIDE.md](GUIDE.md) → *Build status*.
</content>
</invoke>
