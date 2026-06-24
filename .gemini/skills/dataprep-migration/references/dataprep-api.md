# Dataprep v4 API — authoritative how-to

The Dataprep (Trifacta) v4 REST API as proven against a real audit of **87 flows / 14 plans /
~3000 job runs**. This is the source of truth for discovery-time API calls. Auth: API access token
in the `Authorization: Bearer <token>` header.

> **READ-ONLY guarantee.** Discovery uses **GET only**. Never call any write/run/delete endpoint
> (no creating, editing, executing, or deleting flows/plans/jobs). The toolkit only ever *reads*
> the Dataprep environment; all writes go to the disposable BigQuery staging dataset.

## The two silent killers — always set these params

Every list endpoint (`/v4/flows`, `/v4/plans`, `/v4/jobGroups`, `/v4/planSnapshotRuns`) has two
defaults that silently corrupt the catalog with **no error raised**:

1. **25-item pagination cap.** With no `limit`, you get exactly 25 items. Always append
   **`limit=250`** (or higher). Without it the catalog truncates and you lose flows/plans/jobs.
2. **Owner-only scope.** By default lists return only resources OWNED by the token's user —
   missing team-shared flows and ex-employees' flows. Always append **`flowsFilter=all`** /
   **`plansFilter=all`** to widen scope to everything the credentials are authorized to view.

```
GET /v4/flows?limit=250&flowsFilter=all
GET /v4/plans?limit=250&plansFilter=all
```

For large environments, paginate explicitly (offset/cursor) past the first 250 until the page
returns fewer than `limit` items.

## Endpoints

| Endpoint | Use | Required params |
|---|---|---|
| `GET /v4/flows` | List flows (seed catalog) | `limit=250&flowsFilter=all` |
| `GET /v4/flows/{id}/package` | Export one flow ZIP (identical to UI "Export Flow") | — |
| `GET /v4/plans` | List plans + embedded last-run | `limit=250&plansFilter=all` |
| `GET /v4/jobGroups` | Bulk job history (creator, durations) | `limit=250&embed=creator` |
| `GET /v4/planSnapshotRuns` | ⚠ AVOID for active-plan mapping (see below) | — |

## Pitfall: planSnapshotRuns vs latestPlanSnapshotRun

Executing a plan creates a **transient snapshot instance** first. `/v4/planSnapshotRuns` records
reference only that snapshot ID — not the master plan ID from `/v4/plans` — so mapping runs back to
master plans through it is fragile and 403-prone. The result: **active plans falsely report
"Never Run".**

**Fix:** do NOT use `/v4/planSnapshotRuns` to map active plans. Read the embedded
**`latestPlanSnapshotRun`** dict directly off each plan object:

```
GET /v4/plans?limit=250&plansFilter=all
→ plan.latestPlanSnapshotRun { status, createdAt }
```

The API natively embeds the most recent run there, bypassing all ID-mapping and permission issues.

## Pitfall: jobGroups nested filtering 500s → bulk + aggregate in memory

Filtering `/v4/jobGroups` on nested fields (e.g.
`?filterFields=wrangledDataset.flow.id&filter=12345&filterType=exact`) fails with a server-side
**500 IOException**. You cannot query job history flow-by-flow through the API.

**Fix:** bulk-paginate the last ~1000–3000 jobs in pages of ~100 and aggregate **entirely in
memory** (runs in <5s, no API failures):

```
GET /v4/jobGroups?limit=250&embed=creator   (paginate to ~3000 jobs)
```

### Creator, runner-email sets, durations (per flow)

`&embed=creator` adds a creator dict to each job group:

```json
"creator": { "id": 590534, "email": "analyst@yourcompany.com", "name": "Jane Analyst" }
```

Aggregate per flow:
- **Creator** → `creator.name`, `creator.email` (default `"Unknown"` if absent).
- **Unique runner emails** → maintain a `set()` per flow ID; add each `creator.email`, dropping
  `"Unknown"`/`"N/A"`; join with `", "` (→ `None` if empty) for a DB-ready string.
- **Avg run duration** → the API exposes no duration field; compute per job as
  `updatedAt − createdAt` (ISO-8601; replace trailing `Z` with `+00:00` before parsing), then
  average in memory.

## Windows / OneDrive workarounds (touch discovery output)

- **MAX_PATH (260):** deep JSON5 package trees + long flow names overflow the path limit and cause
  silent extraction failures. **Sanitize extracted folder names to ≤60 chars and drop flow-ID
  suffixes** before unzipping into `context/`.
  ```python
  def get_clean_folder_name(name):
      s = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)
      s = re.sub(r'_+', '_', s).strip('_')
      return s[:60].strip('_')
  ```
- **OneDrive exclusive locks:** writing catalog/report files into a synced dir can throw
  `PermissionError` (WinError 32) when the target is open. Wrap writes in a try/except that falls
  back to an alternate filename so discovery never halts:
  ```python
  try:
      writer.save()                 # primary
  except PermissionError:
      writer.save("output/data/catalog_database_ready.xlsx")   # fallback
  ```

## Discovery script sequence (read-only)

The end-to-end discovery run, in order:

1. **Sweep** — `GET /v4/flows?limit=250&flowsFilter=all`; save live flow metadata to JSON.
2. **Download + unzip** — read that JSON, compute clean folder names (no flow IDs), download each
   `GET /v4/flows/{id}/package` ZIP, extract to `context/<plan>/<clean_name>/`.
3. **Analyze** — parse each package `.json5` for recipe step counts and transform verbs.
4. **Job stats** — bulk-fetch up to ~3000 jobs with `embed=creator`; compute durations, runner
   names/emails per flow.
5. **Plan stats** — read `latestPlanSnapshotRun` from `GET /v4/plans?limit=250&plansFilter=all`
   for active/stale plan run-state. (`/v4/planSnapshotRuns` is only an optional, fragile fallback.)
6. **Compile** — merge flows + plans + job stats into the backlog, `docs/catalog.json`, and the
   styled catalog spreadsheet.
