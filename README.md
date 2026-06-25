# Dataprep → BigQuery Migration Kit — project root

This repository has **two layers**:

| Layer | Where | What it's for |
|---|---|---|
| **The toolkit** (the app we built) | [`toolkit/`](toolkit/) | Self-contained Gemini CLI toolkit that migrates Dataprep flows to BigQuery SQL. Run it from inside `toolkit/`. |
| **The handoff / dev context** | this root | Context for *continuing to build the toolkit* in Gemini — so it can be evolved on any machine. |

## If you want to **run** a migration
→ go into [`toolkit/`](toolkit/) and follow [`toolkit/SETUP.md`](toolkit/SETUP.md). Open it in a
browser? See [`toolkit/docs/operators-guide.html`](toolkit/docs/operators-guide.html).

## If you want to **continue building / changing** the toolkit (in Gemini)
1. Open Gemini CLI at this repo root. It auto-loads [`GEMINI.md`](GEMINI.md) — the dev context.
2. Read [`HANDOFF.md`](HANDOFF.md) — what we built, why, current status, and how to continue.
3. Paste [`PROMPT.md`](PROMPT.md) to kick off a focused working session.

## Why it's split this way
The toolkit is meant to be picked up and evolved by Gemini going forward. Keeping the toolkit
self-contained in `toolkit/` (its own `GEMINI.md`, agents, skill, commands) means it still runs
cleanly, while this root carries the human/AI handoff context for making changes — separate from
the thing being changed.

## The toolkit at a glance
Migrates Dataprep (Trifacta) flows into maintainable, **single-file BigQuery SQL**, one flow at a
time, with **frozen-input exact-match parity** verification, a **status lifecycle** (Not started →
In process → Validating → Parallel runs → Productionized), **governance + human sign-off**, and
generated docs. Production and Dataprep stay **read-only**. Full detail in
[`toolkit/GUIDE.md`](toolkit/GUIDE.md).
