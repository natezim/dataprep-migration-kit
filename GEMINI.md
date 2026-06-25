# GEMINI.md — dev context for evolving this project

You are an engineering collaborator helping evolve the **Dataprep → BigQuery Migration Kit**.
This file is the *development* context (auto-loaded at the repo root). It is NOT the toolkit's
runtime rules — those live in [`toolkit/GEMINI.md`](toolkit/GEMINI.md) and load when migrations
are run from inside `toolkit/`.

## What this project is

A self-contained Gemini CLI toolkit (in `toolkit/`) that migrates Dataprep (Trifacta) flows into
maintainable, single-file BigQuery SQL — one flow at a time, verified against the legacy output,
without ever modifying Dataprep or production. Read [`HANDOFF.md`](HANDOFF.md) for the full
picture and current status before making changes.

## The toolkit lives in `toolkit/` — where to change what

| To change… | Edit |
|---|---|
| A runtime rule the migration must always follow | `toolkit/GEMINI.md` |
| A slash command (`/dp:start`, `/dp:migrate`, `/dp:signoff`) | `toolkit/.gemini/commands/dp/*.toml` |
| An agent's behavior (`@flow-inventory`, `@recipe-translator`, `@parity-auditor`, `@governance`) | `toolkit/.gemini/agents/*.md` |
| A Wrangle→SQL mapping, parity rule, API/env finding, output/governance standard | `toolkit/.gemini/skills/dataprep-migration/references/*.md` |
| Discovery scripts | `toolkit/scripts/*.py` |
| Human-facing docs | `toolkit/README.md`, `GUIDE.md`, `SETUP.md`, `CONTRIBUTING.md`, `MAINTAINING.md` |

The capture-it-back-into-references workflow is in `toolkit/MAINTAINING.md` — follow it.

## How to make changes

- **Small, focused commits.** One change = one commit with a clear message.
- **Keep references concrete:** real Wrangle in, real SQL out, the gotcha noted.
- **Update the docs you touch** so they don't drift (the toolkit's docs are the source of truth).
- When you change behavior, say what you changed, where, and why.

## Non-negotiables — do not let changes erode these

1. **One flow at a time.** Discovery (read-only inventory) is the only bulk step.
2. **Dataprep is read-only** (only `GET` — list/export); **production is read-only** (SELECT-only).
   All writes go to the disposable `dataprep_migration_staging` dataset.
3. **No hard-coded values** ship — dates/params become `DECLARE` / `CURRENT_DATE()` / query params.
4. **Exact-match parity on a frozen input.** Never weaken the audit to make a flow pass.
5. **Never auto-promote.** `Productionized` requires `/dp:signoff` — a human attestation. The team
   owns the migration; Gemini assists, humans validate.
6. **SQL-first, one self-contained file** per flow; Dataform `.sqlx` is optional.

## Platform note
Built/tested on Windows (PowerShell). Watch the known gotchas in
`toolkit/.gemini/skills/dataprep-migration/references/windows-onedrive.md` (MAX_PATH, file locks).
Don't put the git repo inside a OneDrive/SharePoint-synced folder.
