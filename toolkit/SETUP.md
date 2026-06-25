# Setup — get running today

You don't copy this folder per flow. **One clone = the whole project.** Open Gemini CLI inside
it and work one flow at a time.

## 1. Prerequisites

- **Gemini CLI**, 2026-era — needs skills (≥ v0.24) and subagents (≥ v0.38.1).
  Check: `gemini --version`. If older, update first or the agents/skill won't load.
- **git** (you already have the repo).
- **BigQuery access** — your Google login with read on the source data and write on a staging
  dataset. **No gcloud install needed** (we use the Python client's browser OAuth, or the
  BigQuery console / Dataform UI).
- **Python 3.10+** *(only if you'll use the Python target or run parity from a script)* —
  then `pip install -r requirements.txt`.
- **Dataprep access** — a Personal Access Token *(optional — only speeds up export; the UI
  "Export Flow" button works without it)*.

## 2. Point Gemini at the project

Use the working copy that's already here, or clone fresh:

```powershell
# Option A — use the copy already on disk:
cd "C:\Users\user\Documents\Claude Code\dataprep-migration-kit"

# Option B — clone somewhere new:
git clone https://github.com/natezim/dataprep-migration-kit
cd dataprep-migration-kit
```

Do **not** put this folder inside a OneDrive/SharePoint-synced location (it corrupts `.git`).

## 3. Configure

```powershell
Copy-Item .env.example .env
```
Edit `.env`:
- `DATAPREP_API_BASE_URL` — your Dataprep host (or leave default; only needed for API export).
- `DATAPREP_API_TOKEN` — your PAT (optional; skip if you'll export from the UI).

Edit `workflow_settings.yaml` (only needed if you use the optional `.sqlx` Dataform wrapper):
- `defaultProject` — your GCP project id.
- `defaultDataset` — keep `dataprep_migration_staging` (the disposable staging dataset).
- `defaultLocation` — your BigQuery region (e.g. `US`).

## 4. First run

```
gemini      →   /dp:start
```

`/dp:start` does first-time setup: it confirms your project/dataset, checks whether you have
Dataprep API access (and falls back to UI export if not), and offers to run discovery. Then:

1. **Export one flow** — API (`GET /v4/flows/{id}/package`) or the UI **Export Flow** button —
   and unzip it into `flows/<plan>/<flow>/recipe/`.
2. Run **`/dp:migrate <flow>`** for that one flow. Everything it produces — `<flow>.sql`,
   `validation.sql`, `EXPLANATION.md`, `parity.md` — lands in `flows/<plan>/<flow>/`.
3. Review the output, run `validation.sql` yourself, read `parity.md`. Commit.
4. When satisfied, run **`/dp:signoff <flow>`** to attest you validated it → the flow's status
   advances to **Productionized**.

**One flow at a time.** Bulk runs are refused by design; only read-only discovery is bulk.
**Status changes are gated** — Gemini confirms with you before advancing a flow.

## 5. Track progress

The live tracker `status/migration_status.csv` (+ Excel) records each flow's stage —
**Not started → In process → Validating → Parallel runs → Productionized** — against the total
inventory. `/dp:start` reads it to pick the next flow and resume in-progress work.

## 6. See the status tracker

Just open **`status/migration_status.xlsx`** in Excel (or `status/migration_status.csv` in any
viewer). No server, no hosting — it's a plain file that the toolkit updates as flows progress.

## First-run reality check

The transform dictionary is drafted from known Wrangle semantics. Your **first real recipe**
is what hardens it — expect to iterate on the dictionary/agents for the first few flows. That's
normal and exactly what the parity audit is there to catch.
