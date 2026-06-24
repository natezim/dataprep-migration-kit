# Master Migration Playbook: Google Cloud Dataprep to BigQuery Standard SQL
**Version:** 1.0 (Sanitized Production Release)  
**Classification:** General Technical Standards (Public / Reusable)  
**Purpose:** Standard blueprint and architectural template for migrating legacy Dataprep (Trifacta) wrangle pipelines into optimized, self-cleaning Dataform models and BigQuery Standard SQL scripts, guaranteeing 100% exact data parity.

---

## 📋 1. Executive Mission & Core Directive

The goal of this playbook is to establish a repeatable, standardized, and highly efficient path to translate legacy Dataprep flows into maintainable **Google SQL (BigQuery Standard SQL)**. 

### The Core Mandates:
1. **Google SQL First:** BigQuery Standard SQL is our primary target lane. Python is deprecated and should only be used as a rare exception if SQL is functionally incapable of expressing the logic.
2. **Unified Single-Script Delivery:** To maximize ease of maintenance, all GCS source mounting, SQL transformations, and staging table loading must be consolidated into **one single, unified, self-contained SQL file**.
3. **Database Cleanliness & Staging Hygiene:** Temporary external tables created during GCS file ingestion must be completely cleaned up and dropped at the end of every execution block.
4. **Dual-Deliverable Standard:** Every migrated flow must produce two final artifacts:
   * A Dataform model (`.sqlx`) for repository compilation and automated orchestration scheduling.
   * A pure SQL copy-paste script (`.sql`) for direct execution in the BigQuery Query Editor (GCP) with zero edits.

---

## 🛠️ 2. Architectural Design Pattern: The "Create-Execute-Clean" Lifecycle

Every migrated pipeline must follow a strict three-phase lifecycle executed within a single, sequential SQL script (using a Dataform `type: "operations"` with `hasOutput: true` block):

```
 PHASE 1: CREATE (DDL)             PHASE 2: EXECUTE (DML)             PHASE 3: CLEAN (DDL)
 
┌────────────────────────┐        ┌────────────────────────┐        ┌────────────────────────┐
│ CREATE EXTERNAL TABLE  │        │ CREATE TABLE AS        │        │ DROP EXTERNAL TABLE    │
│ Mounts raw GCS CSV     │ ──────>│ Multi-stage CTE graph  │ ──────>│ Drops GCS tables,      │
│ files as virtual tables│        │ Runs Wrangle transforms│        │ leaving schema pristine│
└────────────────────────┘        └────────────────────────┘        └────────────────────────┘
```

### Phase 1: Create (Mounting Sources)
Declare BigQuery External Tables directly pointing to GCS CSV resources. This lets BigQuery parse the CSV files on-the-fly dynamically.
* **Important:** If raw CSV columns contain unescaped newline characters inside double quotes (a major source of parsed row truncation), you **must** append `allow_quoted_newlines = true` in the OPTIONS block.

```sql
CREATE OR REPLACE EXTERNAL TABLE `my-gcp-project.STAGING_DATASET.EXT_USER_ALLOC` (
  Assigned_to STRING,
  Email STRING,
  User_ID STRING,
  Employee_Status STRING,
  License_key STRING,
  Created STRING
)
OPTIONS (
  format = 'CSV',
  uris = ['gs://my-data-bucket/Tableau/Tableau_User_allocations.csv'],
  skip_leading_rows = 1,
  quote = '"',
  field_delimiter = ',',
  allow_quoted_newlines = true -- Handles quoted newline characters in keys
);
```

### Phase 2: Execute (CTEs Transformation Graph)
Write the main transformation graph to load the target staging table.
* **CTEs Alignment:** Every CTE inside the `with` block should correspond to a single, distinct recipe node/node-type from the legacy Dataprep flow (e.g. `installs`, `active_usage`, `user_map`, etc.), fully comment-documented with its original legacy recipe ID.
* **Explicit Column Selection:** Never use `SELECT *` in joins. Always coalesce, cast, and alias columns explicitly.

### Phase 3: Clean (Pristine Schema Drop)
At the very bottom of your script, immediately execute drop DDL statements to remove the temporary external tables. This ensures the shared staging schema is never cluttered with temporary pipeline definitions.

```sql
DROP EXTERNAL TABLE IF EXISTS `my-gcp-project.STAGING_DATASET.EXT_MY_KEYS`;
DROP EXTERNAL TABLE IF EXISTS `my-gcp-project.STAGING_DATASET.EXT_USER_ALLOC`;
```

---

## 🐛 3. Legitimate Parity Quirks & Corruption Defense

During parity audits, you will encounter discrepancies between BigQuery SQL and the old Dataprep engine. Standardize your query translations with these exact behaviors:

### A. Replicating Legacy Trailing Newlines (The Failed-Join Bug)
* **The Issue:** Unescaped trailing newlines (`\n`) in quoted GCS fields will be read literally by BigQuery as `TCVA-A9A2...\n`. If legacy Dataprep did not clean them, joining on this field with other tables will fail to match.
* **The Resolution:** 
  * **Strict Parity Mode (For Validation):** To achieve a 100% exact bit-by-cell matched validation against the old production table, you must join on the raw, uncleaned keys, deliberately reproducing the legacy join-failures and row-duplications.
  * **Clean Promotion Mode (For Release):** For final production release, clean and trim keys before joining to consolidate duplicate rows and resolve missing metadata:
    `trim(regexp_replace(Key_Name, '^"|"$', '')) as Key_Name`

### B. Date Midnight Normalization (00:00:00 precision)
* **The Issue:** Legacy Dataprep formats dates as strings `yyyy-MM-dd`. When loaded into BigQuery `DATETIME` columns, BigQuery automatically appends midnight `00:00:00`. Direct `safe_cast` of active timestamps containing hours/minutes/seconds will cause cell-level mismatches.
* **The Resolution:** Wrap all cast datetime fields in **`datetime_trunc(safe_cast(... as DATETIME), DAY)`** to truncate datetimes to date-only midnight precision, guaranteeing perfect parity.

### C. Null Propagation Fixes (Coalescing)
* Dataprep treats nulls as empty strings (`""`), whereas SQL-92 propagates nulls (any concatenation with a null becomes null).
* Always apply `coalesce` or `nullif` before string concatenations or joins:
  `coalesce(i.USER_EMAIL, a.USER_EMAIL) as USER_EMAIL_ADDR`

---

## 📄 4. Deliverable File Templates

### Artifact A: The Dataform Model (`.sqlx`)
Saved to `definitions/sas_audit/<flow_name>/<flow_name>.sqlx`. Contains the Dataform configuration block.

```sql
-- Purpose: Unified DDL/DML Staging Pipeline for <Flow Name>
-- Legacy Flow ID: <ID>
-- Date Last Modified: YYYY-MM-DD

config {
  type: "operations",
  hasOutput: true,
  database: "my-gcp-project",
  schema: "STAGING_DATASET",
  name: "STG_MY_TABLE",
  tags: ["plan:My_Parent_Plan", "lob:my_line_of_business"]
}

-- PART 1: REGISTER GCS SOURCES
CREATE OR REPLACE EXTERNAL TABLE `my-gcp-project.STAGING_DATASET.EXT_MY_KEYS` ( ... )
OPTIONS (...);

-- PART 2: MAIN TRANSFORMATION
CREATE OR REPLACE TABLE `my-gcp-project.STAGING_DATASET.STG_MY_TABLE` AS
with my_keys as (
  ...
)
select ... from final_aggregation;

-- PART 3: CLEAN UP TEMPORARY TABLES
DROP EXTERNAL TABLE IF EXISTS `my-gcp-project.STAGING_DATASET.EXT_MY_KEYS`;
```

### Artifact B: The Pure SQL Console Script (`.sql`)
Saved to `output/queries/<table_name>.sql`. Fully copy-paste ready for GCP standard SQL console query editors.

```sql
-- =====================================================================================================================
-- BigQuery Standard SQL: STG_MY_TABLE (Unified External Sources & Transformation Pipeline)
-- Date Last Modified: YYYY-MM-DD
-- =====================================================================================================================
-- RUN INSTRUCTIONS:
--   Simply copy-paste this ENTIRE file directly into the Google Cloud BigQuery Console (GCP) query editor and run!
-- =====================================================================================================================

-- PART 1: REGISTER GCS SOURCES
CREATE OR REPLACE EXTERNAL TABLE `my-gcp-project.STAGING_DATASET.EXT_MY_KEYS` ( ... )
OPTIONS (...);

-- PART 2: MAIN TRANSFORMATION
CREATE OR REPLACE TABLE `my-gcp-project.STAGING_DATASET.STG_MY_TABLE` AS
with my_keys as (
  ...
)
select ... from final_aggregation;

-- PART 3: CLEAN UP TEMPORARY TABLES
DROP EXTERNAL TABLE IF EXISTS `my-gcp-project.STAGING_DATASET.EXT_MY_KEYS`;
```

---

## 🤖 5. Copilot / Developer Prompt to Automate Next Flow
Copy and paste this standard prompt template to automatically translate your next legacy Dataprep flow:

```markdown
You are an expert Google Cloud Dataprep to BigQuery Standard SQL migration agent. I want you to migrate a legacy Wrangle recipe into a unified Dataform-native Standard SQL pipeline (.sqlx) and a standalone BigQuery console script (.sql).

Follow these rules strictly:
1. Pure Google SQL: Implement the transformation graph entirely in standard BigQuery SQL using a Common Table Expression (CTE) graph matching our step-by-step recipe.
2. Self-Cleaning operations block: Put the entire script into a single execution.
   - Part 1: Register GCS CSV files as BigQuery external tables (using options like allow_quoted_newlines = true).
   - Part 2: Load the target table using a CREATE OR REPLACE TABLE AS CTE graph.
   - Part 3: Execute DROP EXTERNAL TABLE IF EXISTS statements at the very bottom to remove all GCS temporary tables immediately.
3. Apply Date Truncations: Use datetime_trunc(safe_cast(... as DATETIME), DAY) to truncate all datetimes to midnight precision, matching Dataprep formatting.
4. Clean strings: Strip double quotes using trim(regexp_replace(col, '^"|"$', '')) as col.
5. Create Dual-Deliverables: Generate a formal `.sqlx` operations model for Dataform, and a clean, standalone copy-paste ready `.sql` script (with config blocks stripped) for the GCP Query Console.

Here is my exported recipe JSON/JSON5 or AST description:
[Paste your recipe steps or flow package JSON here]
```
