# Google Cloud Dataprep API Integration & Developer Handoff Guide

This developer guide documents the crucial technical findings, API behaviors, environment workarounds, and advanced cataloging scripts discovered during the audit of **87 flows, 14 plans, and 3,000 historical job runs**. If a developer or platform administrator needs to update the core Dataprep Migration base package (such as `.gemini/commands/` or `.gemini/agents/` configurations), they should use these findings as their implementation blueprint.

---

## 🔑 1. Critical Dataprep API Integration Findings

### A. The 25-Item Default Limit (Silent Truncation)
* **Behavior:** The Dataprep v4 API endpoints (`/v4/flows`, `/v4/plans`, `/v4/jobGroups`, `/v4/planSnapshotRuns`) enforce a strict, default pagination limit of exactly **25 items** if no limit is passed.
* **Impact on Base Package:** If the base package queries these endpoints without explicitly appending `limit`, the migration catalog will silenty truncate, leaving out flows and plans owned by other team members.
* **Recommendation:** Ensure all base commands or python agents append `limit=250` (or higher) to list queries.

### B. Ownership Filters (`flowsFilter=all` & `plansFilter=all`)
* **Behavior:** By default, `/v4/flows` and `/v4/plans` query only the resources **owned directly** by the user associated with the token.
* **Impact on Base Package:** Standard queries will completely miss collaborative, team-shared pipelines or pipelines created by former employees.
* **Recommendation:** Overrides **must** append `flowsFilter=all` and `plansFilter=all` to the list queries. This expands the scope from "my stuff" to "everything my credentials have authorization to view" across the shared project workspace.

### C. Server-Side Nested Filtering Failure (IOException 500)
* **Behavior:** Attempting to filter the job execution log (`/v4/jobGroups`) on nested fields (e.g., `?filterFields=wrangledDataset.flow.id&filter=12345&filterType=exact`) fails with a server-side `500 IOException`.
* **Impact on Base Package:** Base package agents cannot query job history on a flow-by-flow basis through the API directly.
* **Recommendation:** Perform **bulk pagination fetching** (e.g. pulling the last 1,000 to 3,000 jobs in pages of 100) and compile the stats **entirely in memory** inside your python scripts. This is extremely fast (running in under 5 seconds) and avoids API failures.

### D. Plan Snapshot Runs vs. Master Plan IDs
* **Behavior:** Executing a Plan creates a snapshot instance first. The `/v4/planSnapshotRuns` history records only reference this transient snapshot ID, not the master plan ID returned by `/v4/plans`. This makes mapping runs back to master plans via the snapshot endpoint extremely fragile and prone to 403 authorization blocks.
* **Impact on Base Package:** Traditional run-mapping will report active plans as "Never Run".
* **Recommendation:** Do not use `/v4/planSnapshotRuns` to map active master plans. Instead, read the embedded **`latestPlanSnapshotRun`** dictionary directly from each master plan object returned by `GET /v4/plans?limit=250&plansFilter=all`. The API natively embeds the most recent run details (status, createdAt) directly inside the plan object, bypassing all permission and ID-mapping issues.

---

## 💻 2. Windows & OneDrive Environment Workarounds

### A. MAX_PATH Violations (260-Character Path Limits)
* **Behavior:** Dataprep unzipped packages contain deep JSON5 file structures. Combining a deep local directory path with extremely long descriptive flow names (especially under synced business folders like OneDrive) will exceed the Windows `MAX_PATH` limit (260 characters), causing silent extraction failures.
* **Impact on Base Package:** Extraction tasks will fail with `FileNotFoundError` or `PermissionError`.
* **Recommendation:** Sanitize and truncate the extracted folder names to a maximum of 60 characters and remove the Flow ID suffixes to keep directory trees shallow and human-readable, e.g.:
  ```python
  def get_clean_folder_name(name):
      sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)
      sanitized = re.sub(r'_+', '_', sanitized).strip('_')
      return sanitized[:60].strip('_')
  ```

### B. Synced-Folder Exclusive Locks (Permission Denied)
* **Behavior:** When generating reports, Excel sheets, or metadata files inside OneDrive-synced directories, the Windows file system and OneDrive sync engine will place immediate exclusive locks on newly opened or created files.
* **Impact on Base Package:** Attempting to overwrite an active Excel spreadsheet (`catalog.xlsx`) that is currently open on a user's machine will throw a python `PermissionError` (WinError 32).
* **Recommendation:** Wrap all pandas Excel saves in a fail-safe write-block. If a permission error is caught (file is locked), automatically write the data to an alternate fallback name so the script never halts:
  ```python
  try:
      # Primary write
      writer.save()
  except PermissionError:
      # Graceful fallback
      fallback_path = "output/data/catalog_database_ready.xlsx"
      writer.save(fallback_path)
  ```

---

## 📊 3. User & Execution Metrics Retrieval (Advanced Analytics)

To turn a basic flow catalog into an operational, database-ready dashboard, the following data-extraction methodologies must be applied programmatically:

### A. Splitting Owner Name & Email (Query & Parse)
To separate the user who ran the flow into distinct database columns (rather than a combined string), append `&embed=creator` to the `/v4/jobGroups` query. 
* **API Response Schema:**
  ```json
  "creator": {
    "id": 590534,
    "email": "analyst@yourcompany.com",
    "name": "Jane Analyst"
  }
  ```
* **Extraction Parsing (Python):**
  ```python
  creator = jg.get("creator", {})
  last_run_by_name = creator.get("name", "Unknown")
  last_run_by_email = creator.get("email", "Unknown")
  ```

### B. Compiling Comma-Separated Unique Runner Emails
To generate a clean, comma-separated list of runner emails (filtering out placeholders like `"Unknown"` or `"N/A"`), maintain a Python `set` of emails per Flow ID during the job log loop, then join them with a comma:
* **Aggregation Logic (Python):**
  ```python
  # Set up the set
  stats["runner_emails"] = set()
  
  # Inside loop over jobs:
  if creator_email and creator_email != "Unknown" and creator_email != "N/A":
      stats["runner_emails"].add(creator_email)
      
  # Formatting when compiling:
  unique_runners_str = ", ".join(stats["runner_emails"]) if stats["runner_emails"] else "None"
  ```
This yields a database-ready string (e.g. `analyst@yourcompany.com, manager@yourcompany.com`) that can be loaded into BigQuery or easily joined with employee directories.

### C. Calculating Run Durations and Averages
Because the API does not expose execution durations directly in list endpoints, calculate each job's runtime dynamically by subtracting the `createdAt` datetime from the `updatedAt` datetime of the job group, then average them in memory:
* **Duration Parsing (Python):**
  ```python
  c_dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
  u_dt = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
  duration_secs = (u_dt - c_dt).total_seconds()
  stats["run_durations"].append(duration_secs)
  ```

---

## 📑 4. Programmatic Excel Generation & Auto-Formatting

To output a professional Excel catalog dynamically with dual sheets and automatic auto-fit column styling, use the `pandas` library with the `openpyxl` engine.

### A. Python Code Blueprint (Excel Tab Generation)
```python
import pandas as pd
import os

# Create DataFrames for both tabs
df_catalog = pd.DataFrame(catalog_data)
df_definitions = pd.DataFrame(complexity_definitions_data)

excel_path = "output/data/catalog.xlsx"
os.makedirs(os.path.dirname(excel_path), exist_ok=True)

try:
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # Write tab 1: Catalog summary
        df_catalog.to_excel(writer, sheet_name="Dataprep Catalog Summary", index=False)
        
        # Write tab 2: Complexity reference guide
        df_definitions.to_excel(writer, sheet_name="Complexity Definitions", index=False)
        
        # Access openpyxl objects to dynamically auto-fit columns
        # Tab 1 Formatting
        ws_summary = writer.sheets["Dataprep Catalog Summary"]
        for col in ws_summary.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_summary.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 55)
            
        # Tab 2 Formatting
        ws_defs = writer.sheets["Complexity Definitions"]
        for col in ws_defs.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_defs.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 65)
            
    print(f"Excel catalog successfully saved at {excel_path}")
except PermissionError:
    # Handle active Windows File Locking gracefully
    fallback_path = "output/data/catalog_database_ready.xlsx"
    print(f"File is locked. Fallback written to {fallback_path}")
    # (re-run save block using fallback_path)
```

---

## ⚙️ 5. Step-by-Step Script Execution Sequence

To fetch and compile the entire environment, run the scripts in the following exact sequence:

1. **`python output/temp/test_api.py`**
   * *Purpose:* Performs the broad API sweep (`limit=250` and `flowsFilter=all`). Securely reads `.env` variables and saves all live flows metadata to `output/temp/real_flows.json`.
2. **`python output/temp/download_and_unzip_all_clean.py`**
   * *Purpose:* Reads `real_flows.json`, calculates clean folder names (NO flow IDs appended), downloads package ZIPs, and extracts them to `context/sas_audit/<clean_folder_name>/`.
3. **`python output/temp/analyze_all_flows.py`**
   * *Purpose:* Performs highly optimized metadata lookups on each extracted package's `.json5` file, compiling total recipe step counts and transform verbs. Saves outputs to `output/temp/flow_analysis.json`.
4. **`python output/temp/fetch_job_stats.py`**
   * *Purpose:* Fetches up to 3,000 historical runs with embedded creators (`embed=creator`), calculates runtime averages, maps runner names and emails, and outputs `output/temp/flow_run_stats.json`.
5. **`python output/temp/fetch_plan_run_stats.py`** (Optional fallback)
   * *Purpose:* Pulls up to 300 Plan snapshot runs, mapping active/stale orchestrations.
6. **`python output/temp/compile_ultimate_backlog.py`**
   * *Purpose:* Performs the final consolidation. Merges flows, plans, and 3,000-run statistics. Generates `docs/catalog.json`, `output/backlog.md`, and the dual-sheet styled spreadsheet `output/data/catalog_database_ready.xlsx`.
