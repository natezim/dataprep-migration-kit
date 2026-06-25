# Kickoff prompt

Paste the block below to start a focused session in Gemini (run from this repo root) to continue
building the toolkit.

---

```
You are my engineering collaborator for the Dataprep → BigQuery Migration Kit.

The toolkit lives in `toolkit/`. Before doing anything, read:
- `GEMINI.md` (this project's dev context + the non-negotiables)
- `HANDOFF.md` (what we built, why, and current status)
- `toolkit/GUIDE.md` (how the toolkit works end to end)
- `toolkit/MAINTAINING.md` (the hardening loop and where each kind of change goes)

Then summarize back to me, in a few lines: what this toolkit does, its current status, and the
non-negotiables — so I know you've got the context.

Working rules:
- Make small, focused changes. One change = one commit with a clear message.
- To change behavior, edit the right file in `toolkit/`: a command in
  `toolkit/.gemini/commands/dp/`, an agent in `toolkit/.gemini/agents/`, a reference in
  `toolkit/.gemini/skills/dataprep-migration/references/`, or a rule in `toolkit/GEMINI.md`.
- Keep references concrete (real Wrangle in, real SQL out, the gotcha noted) and update any doc
  you touch so it doesn't drift.
- NEVER break the non-negotiables: one flow at a time; Dataprep and production read-only (all
  writes go to dataprep_migration_staging); no hard-coded values; exact-match parity on a frozen
  input; never auto-promote (Productionized needs human /dp:signoff); SQL-first single file.
- After each change, tell me what you changed, where, and why.

Don't start migrating flows yet — first confirm you understand the project. Then ask me what I
want to work on.
```
