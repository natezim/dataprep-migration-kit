# Prompt to give Claude (in chat) to build the PowerPoint

Paste everything inside the code block into a fresh Claude.ai conversation. This version is
technical — it explains how the system is built and how it works, not just the pitch.

---

```
Create a polished, technical PowerPoint presentation (.pptx I can download) from the content below.

AUDIENCE & TONE:
- Audience is technical leadership + senior data engineers. I am the presenter.
- Goal: explain how we built an AI-assisted Dataprep→BigQuery migration system, how it works,
  and get approval to run a pilot.
- Be concrete and technical. Avoid fluff and marketing adjectives. Prefer mechanisms, data
  flows, and named technologies over vague benefits.

DESIGN:
- Clean modern technical theme, 16:9, one accent color, generous white space, monospace for
  code/paths/identifiers.
- Short bullets on slides (max ~6, ~1 line). Put deeper detail in the SPEAKER NOTES.
- Use real PowerPoint tables for slides marked (table). Use simple boxes/arrows for diagrams.
- Slide numbers. Keep [bracketed] items as visible placeholders.

SLIDES:

Slide 1 — TITLE
Dataprep → BigQuery Migration System
Subtitle: AI-assisted, verifiable migration of Dataprep flows to maintainable SQL and Python
Footer: [Your name] · [Team] · [Date]

Slide 2 — Executive Summary
- ~100 Dataprep flows (organized in Plans) → owned, version-controlled BigQuery assets
- A repeatable toolkit converts each flow to commented Dataform SQL or Python
- Every migration is verified against live Dataprep output before promotion; production is never touched
- Ask: approve a 3–5 flow pilot
SPEAKER NOTES: One slide for execs who won't read the rest. The next 12 slides are how it actually works.

Slide 3 — The Problem (technically)
- Dataprep flows are visual "recipes" written in Wrangle, a declarative DSL
- At run time Dataprep compiles Wrangle to Apache Beam (Dataflow) or pushdown SQL (BigQuery)
- The logic is locked in a GUI: no Git, no diffs, no tests, no lineage, no code review
- Maintenance and knowledge depend on the tool and a few people
SPEAKER NOTES: Because Wrangle is a finite, declarative DSL, migration is a *transpilation* problem — not a from-scratch rewrite. That's the key technical insight the whole system rests on.

Slide 4 — What We Built (architecture)
- Gemini CLI as the driver, with project-scoped agents, skills, and slash-commands
- A transform dictionary: Wrangle step → BigQuery SQL / pandas / PySpark mappings (reviewed, reused)
- Target: Dataform (SQL, dependency-managed) and Python (bigframes/pandas/PySpark)
- Verification engine + generated catalog + docs, all in Git
SPEAKER NOTES: Diagram suggestion — left: Dataprep (flow packages); middle: the toolkit (3 agents + dictionary); right: BigQuery (staging + prod) + Git/Pages. Arrows: extract → translate → verify → document → cut over.

Slide 5 — How We Built It: the toolkit internals
- @flow-inventory — parses a flow package → backlog, dependency DAG, complexity, target, catalog entry
- @recipe-translator — recipe → commented code, one block per Wrangle step, original step quoted
- @parity-auditor — runs output into staging and diffs it against live Dataprep output
- /start (orient + pick one flow) and /migrate (run the golden path for one flow)
SPEAKER NOTES: Each agent runs in an isolated context window. The transform dictionary means the translator applies reviewed mappings rather than improvising, so 100 flows come out consistent.

Slide 6 — Extraction: getting the logic out
- A flow package (ZIP) holds flow.json, recipes/ (raw Wrangle), inputs/, outputs/
- Two ways in, identical artifact: Dataprep API (GET /v4/flows/{id}/package) or UI "Export Flow"
- Dependency graph is reconstructed from flow nodes + edges (inputFlownode → outputFlownode)
- API-optional by design: business units without API access use UI export; everything downstream is the same
SPEAKER NOTES: The API only saves clicking and auto-enumeration. It is not load-bearing — the catalog can be seeded from the flow list and packages exported one at a time.

Slide 7 — Translation: transpile-first, native as a rare accelerator
- Primary engine: our transform dictionary maps each Wrangle step to SQL/Python; pushdown SQL reused for BigQuery-source flows
- Dataprep's own code-gen (POST /v4/outputObjects/<id>/wrangleToPython) is deprecated (R9.7), Enterprise-only, CSV-only, no multi-dataset — used only when it cleanly applies
- Output: one CTE (SQL) or one block (Python) per recipe step, with the original Wrangle quoted
- Three corruption fixes applied up front: timezone-naive temporals, decimal ≤38 digits, coalesce-before-concat
SPEAKER NOTES: We tested the native path and it's too limited and deprecated to depend on. The dictionary-based transpiler is the engine; native gen is an occasional shortcut.

Slide 8 — SQL vs Python (table)
Columns: Use | Target | Why
Rows:
- Filters, joins, aggregations, pivots, dedupe | Dataform SQL (.sqlx) | Set-based, dependency-managed, pushed down to BigQuery
- Regex/parsing chains, row-wise/iterative logic, fuzzy match, ML/Vertex | Python (bigframes/pandas/PySpark) | Not expressible/readable in SQL
- Mostly SQL with one hard step | Hybrid | SQL bulk + one Python step in the graph
SPEAKER NOTES: Default to SQL for readability and zero-install maintenance; escalate to Python only when SQL can't express it.

Slide 9 — The Verification Engine (the core guarantee)
- Freeze the input: snapshot the source via BigQuery time-travel so both engines see identical data
- Run the migrated code into a disposable staging dataset; run/refresh Dataprep for the baseline
- 4-tier diff: schema → row count → MD5 row-hash → cell-level coordinate scan
- Exact-match bar; normalize known-legit diffs (column order, float rounding, row order, timezone) first
SPEAKER NOTES: Freezing the input is what makes the comparison deterministic — any difference is a logic difference we catch, not data drift. The MD5 row-hash makes the deep compare cheap at scale.

Slide 10 — Safety & Access Model
- Production is read-only: the toolkit issues only SELECTs against prod; never DDL/DML
- All writes go to a disposable staging dataset with a default table expiration (self-cleans)
- Write-guard: any write whose target isn't the staging dataset is refused
- No gcloud required: Python BigQuery client (browser OAuth) or the BigQuery console / Dataform UI
SPEAKER NOTES: We can't assume a locked-down service account (access is user-OAuth), so safety is enforced by read-only operations + a write-guard + an isolated, expiring staging area — not just policy.

Slide 11 — Orchestration: preserving the Plans
- A Dataprep Plan = which flows run, in what order, on what schedule
- Each Plan migrates to a Dataform tag-group + scheduled run, or a Cloud Composer (Airflow) DAG
- Run order comes from data dependencies (ref()) plus any explicit Plan sequencing
- Schedules are carried over, so today's behavior is preserved
SPEAKER NOTES: We migrate Plans, not just flows — otherwise we'd keep the logic but lose the "what runs when."

Slide 12 — Maintainability, Docs & Tracking
- Folders mirror Dataprep: Plan → flow; one self-describing folder per flow (model + README + parity)
- Every artifact has a plain-English header + one commented block per original step
- Generated, drift-proof docs: an HTML+JSON catalog dashboard, per-Plan and per-flow READMEs
- Version-controlled in Git; catalog auto-published to Pages on every change
SPEAKER NOTES: Docs are generated from the same metadata the code uses, so they can't drift. The catalog is the team's "what do we have and what's its status" view, hosted, not a file passed around.

Slide 13 — Workflow Discipline: one flow at a time
- One flow = one branch = one session = one commit — individually reviewable
- The only bulk step is discovery (read-only inventory of all flows)
- /start enforces it: shows progress, finishes in-progress work first, helps pick the next flow
SPEAKER NOTES: This is deliberate. Bulk migration is how you get an unreviewable mess; sequential, verified, committed units keep risk and review load low.

Slide 14 — Rollout Plan (table)
Columns: Phase | Work | Rough time
Rows:
- 0 · Discovery | Inventory Plans & flows, dependency graph, pick pilot | [~X weeks]
- 1 · Pilot | Prove toolkit + verification on 3–5 representative flows | [~X weeks]
- 2 · Scale | Migrate central backlog in dependency order | [~X weeks]
- 3 · Enablement | Train + hand off to business units with guardrails | [~X weeks]
SPEAKER NOTES: We don't scale until the pilot proves end-to-end correctness.

Slide 15 — What We Need
- Confirm Dataprep API/edition (or accept UI-export path); ideally a read-only role on prod data
- Tooling: BigQuery + Dataform (native), a disposable staging dataset, Git host (GitHub/GitLab)
- People/time: [X]; leadership endorsement to engage business units in Phase 3
SPEAKER NOTES: Most of this is already in our stack — no new platform or licensing.

Slide 16 — Why This Approach (table)
Columns: Option | Speed | Cost | Control | Built-in verification
Rows:
- Manual rewrite | Slow | High labor | High | None
- Commercial migration tool | Fast | License $$ | Lower | Partial
- Our AI-assisted toolkit | Fast | No licensing | High | Yes (4-tier parity)
SPEAKER NOTES: Speed of automation, control of owning the code, and a built-in correctness check — without recurring license cost.

Slide 17 — Risks & Mitigations
- Correctness → frozen-input 4-tier parity + human sign-off
- Hard flows (custom logic, *.data artifacts) → flagged in discovery; central team handles them
- Access/edition limits → UI-export fallback; API-optional design
- Adoption → one-at-a-time golden path, generated docs, browser-based maintenance

Slide 18 — Next Steps
- Approve the pilot (3–5 flows)
- Confirm data access + staging dataset
- Kick off Phase 0 discovery
- Review pilot parity results before committing to scale

When done, give me the downloadable .pptx and list any [bracketed] placeholders I still need to fill in.
```
