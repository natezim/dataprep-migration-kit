# Windows & OneDrive workarounds — keep the toolkit from silently halting

The cataloging/extraction scripts run on Windows under a OneDrive-synced repo. Two environment
hazards will halt a run with no useful traceback unless you defend against them up front. Bake
these into every script that unzips packages, walks deep folder trees, or writes a catalog / Excel
/ report. (From the production audit of 87 flows, 14 plans, 3,000 job runs.)

## 1. MAX_PATH — sanitize + truncate every extracted folder name

Windows caps full paths at **260 characters**. Dataprep packages unzip into deep JSON5 trees, and
long descriptive flow names under a synced OneDrive folder blow past 260 → **silent extraction
failure** (`FileNotFoundError` / `PermissionError`). Don't append flow-ID suffixes — they bloat
the path and hurt readability. Sanitize the folder name to **≤60 chars, alnum + `_ - .` only,
collapsed separators, ID suffix stripped**:

```python
import re

def get_clean_folder_name(name):
    sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)  # only alnum + _ - .
    sanitized = re.sub(r'_+', '_', sanitized).strip('_') # collapse repeated separators
    return sanitized[:60].strip('_')                     # cap at 60, no flow-ID suffix
```

Keeps directory trees shallow and human-readable, e.g.
`flows/sas_audit/<clean_folder_name>/recipe/` — NOT `..._flow_id_4f9a2c8b/`. Apply the same
sanitization to the `<plan>` and `<flow>` segments of every `flows/<plan>/<flow>/` path.

## 2. OneDrive exclusive locks — fallback-write so the script never halts

OneDrive's sync engine places **immediate exclusive locks** on newly created/opened files.
Overwriting an active `catalog.xlsx` that the user has open throws **`PermissionError` (WinError
32)**. Wrap **every** file / Excel / report write in `try/except PermissionError` and write to a
fallback filename instead of crashing:

```python
def safe_write(write_fn, primary_path, fallback_path):
    """write_fn(path) does the actual save; falls back on a Windows lock."""
    try:
        write_fn(primary_path)
        return primary_path
    except PermissionError:                       # WinError 32 — file is locked / open / syncing
        write_fn(fallback_path)                    # e.g. status/catalog_database_ready.xlsx
        print(f"Locked: {primary_path} — wrote fallback {fallback_path}")
        return fallback_path
```

Apply this to the pandas/openpyxl Excel writer and every `status/` artifact —
`status/backlog.md`, `status/migration_status.csv`, `status/migration_status.xlsx`,
`status/migration_status.csv`. The script must complete even if a target file is open in Excel
or mid-sync.

## 3. Don't sync `.git` — keep it out of OneDrive

A `.git` directory inside a OneDrive-synced repo causes sync churn, lock contention, and
occasional index corruption (OneDrive racing Git on pack/lock files). Exclude `.git` from sync
(OneDrive → Settings → Choose folders, or mark the path "Always keep on this device" off / add a
`.git` exclusion) so Git operations don't collide with the sync engine.

## Reminder
Dataprep and production are **READ-ONLY**. These scripts only read the API + GCS and write local
catalog artifacts; the migrated table writes only to the disposable `dataprep_migration_staging`.
