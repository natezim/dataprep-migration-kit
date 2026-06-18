# Dataprep Migration Kit

Migrate Dataprep (Trifacta) flows off Dataprep into **BigQuery SQL (Dataform)** or
**Python**, using Gemini CLI. Output is commented, organized, version-controlled, and
**self-auditing** — every migrated table is automatically compared against the legacy
Dataprep output before it's allowed to ship.

This is a **standalone toolkit**. It does not modify, and does not require, the Gemini CLI
starter kit (`global/`, `project-template/`). It carries its own `GEMINI.md` + `.gemini/` so
it runs entirely on its own — recipients get only this. If a global starter kit happens to be
installed, its rules apply on top (additive). **Two ways to ship it** (same files): run it as
a project folder now, or package it as a Gemini CLI **Extension** for one-command install when
you hand it to lines of business — see [GUIDE.md](GUIDE.md) §7b.

> **Setting up to use it today? → [SETUP.md](SETUP.md).** Prereqs, config, first run.
> **Want to understand how it works? → [GUIDE.md](GUIDE.md).** End to end.

## Quickstart

```powershell
# 1. Export a flow package from Dataprep — API GET /v4/flows/{id}/package, OR the
#    UI "Export Flow" button (identical ZIP; no API access needed). Unzip into:
#    dataprep-migration/context/<plan>/<flow>/

# 2. From the dataprep-migration/ folder, in Gemini CLI:
/dp:start          # orient/resume — pick the next flow, one at a time
/dp:migrate <flow> # the golden path for that one flow
```

`/dp:migrate` runs the full pipeline: inventory → transpile (transform dictionary, SQL or Python)
→ compile & dry-run → 4-tier parity audit against a frozen input → report. You get commented
output plus a pass/fail parity report. **One flow at a time** — bulk runs are refused; only
read-only discovery is bulk.

## What you get per flow

- **SQL flows** → a commented Dataform `.sqlx` in `definitions/<plan>/<flow>/` (one CTE per recipe step)
- **Python flows** → a commented script in `python/<plan>/<flow>/` (bigframes / pandas / PySpark)
- **A parity report** in `output/parity/<plan>/<flow>.md` proving the new table matches the legacy Dataprep table

Folders mirror the Dataprep **Plan → flow** hierarchy and are created by Gemini one at a time
from catalog metadata. Plans are migrated as orchestration units (Dataform tag-group or Cloud
Composer DAG), preserving run order and schedule.

## Folder map

| Path | What |
|---|---|
| `context/<plan>/<flow>/` | Exported recipe input (read-only, gitignored) |
| `definitions/<plan>/<flow>/` | SQL (Dataform `.sqlx`) outputs |
| `python/<plan>/<flow>/` | Python-target flows |
| `output/parity/<plan>/<flow>.md` | Parity evidence; `output/` also holds backlog + logs |
| `plans/<plan>/README.md` | Human-readable Plan map |
| `docs/catalog.json` + `docs/catalog.html` | Generated dashboard (host on Pages) |
| `GEMINI.md` | Project rules + SQL-vs-Python decision rule (auto-loaded from package root) |
| `.gemini/` | The toolkit — agents, skill, `/dp:start` + `/dp:migrate` commands |

## Safety

Production stays read-only (SELECT-only, never DDL/DML). Every write goes to one **disposable
staging dataset** (`dataprep_migration_staging`) with a default table expiration that
self-cleans and is deleted at teardown; a write-guard refuses non-staging writes. **gcloud is
not required** — use the Python `google-cloud-bigquery` client with browser OAuth, or the
BigQuery console / Dataform UI.

## Version control & hosting

Plain **git**, working locally today; add a **GitHub or GitLab** remote later with zero rework.
One flow = one branch (`migrate/<plan>-<flow>`) = one commit. Host the catalog dashboard on
GitHub Pages (`.github/workflows/pages.yml`) or GitLab Pages (`.gitlab-ci.yml`) — both ship
dormant until a remote exists. Do **not** keep the `.git` repo in a OneDrive/SharePoint-synced
folder.

## Status

Scaffolded. The transform dictionary (`.gemini/skills/dataprep-migration/references/`)
is drafted from known Wrangle semantics and **gets hardened against your real exported
recipes during the pilot.** See [GUIDE.md](GUIDE.md) → *Build status*.
