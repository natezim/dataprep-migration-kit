# Maintaining & hardening this toolkit

This toolkit is a **living asset**: it gets more accurate every time you migrate a flow. The
`references/` files are its brain — they are the source of truth Gemini applies. Hardening =
capturing each new finding back into the right reference so the *next* flow benefits. No
outside help required; the loop lives here.

## The hardening loop (do this on every flow)

1. Migrate one flow (`/dp:migrate`).
2. Watch for a gap:
   - a `-- TODO: verify` the translator flagged (a Wrangle step not in the dictionary),
   - a **parity mismatch** (Tier 4 shows a `(key, column)` that differs),
   - a **governance finding** (`@governance` flags a hard-coded value, missing comment,
     missing `validation.sql`/`EXPLANATION.md`, etc.),
   - a new API quirk, or a new environment gotcha.
3. **Capture it** into the right reference (table below), with a concrete example + the flow/date.
4. Commit it (one finding = one small commit). The next flow inherits the fix.

This is exactly how the toolkit was built — it just keeps going without anyone in particular.

## Where each finding goes

| Finding | Put it in |
|---|---|
| New Wrangle step/function → SQL mapping | `.gemini/skills/dataprep-migration/references/wrangle-to-sql.md` |
| New Wrangle → Python mapping (rare) | `.gemini/skills/dataprep-migration/references/wrangle-to-python.md` |
| New silent-corruption / parity quirk | `wrangle-to-python.md` (the corruption list) + `parity-harness.md` |
| New Dataprep API behavior / endpoint quirk | `.gemini/skills/dataprep-migration/references/dataprep-api.md` |
| New Windows/OneDrive/env gotcha | `.gemini/skills/dataprep-migration/references/windows-onedrive.md` |
| New Dataform/output convention | `.gemini/skills/dataprep-migration/references/dataform-conventions.md` |
| New output-quality rule (no-hardcoding, commenting, single-file, validation/EXPLANATION) | `.gemini/skills/dataprep-migration/references/output-standards.md` |
| New governance checklist item / signoff gate | `.gemini/skills/dataprep-migration/references/governance.md` |
| A rule Gemini must always follow | `GEMINI.md` |

## For Gemini itself (internal or otherwise)

When you (Gemini) hit a gap mid-migration, don't just patch the one flow — **propose the
reference update** in the same change, so it's captured. Surface it to the human as: *"this
Wrangle step wasn't in the dictionary; here's the mapping I used and the line to add to
`wrangle-to-sql.md`."* The human reviews and commits. That's how the toolkit learns.

## Non-negotiables (don't let hardening erode these)

- **Never weaken the parity audit to make a flow pass.** If new ≠ legacy, fix the translation
  or document the deviation (Clean Promotion) — never loosen the check.
- **Strict Parity reproduces legacy exactly, bugs and all.** Cleaning is a separate, documented pass.
- **No hard-coded values** ever ship — dates/params become `DECLARE` / `CURRENT_DATE()` / params.
- **Never auto-promote.** Productionized requires `/dp:signoff` — a human attestation. The team
  owns the migration; Gemini assists, humans validate. Status changes are gated.
- **Production and Dataprep stay read-only.** All writes go to the disposable staging dataset.
- **One flow at a time.** Discovery is the only bulk step.
- Keep references concrete: real Wrangle in, real SQL out, with the gotcha noted.

## Reviewing changes

Treat references like code: small commits, clear messages, reviewed via pull request. The
`references/` history becomes the record of everything the team learned migrating Dataprep —
which is itself valuable long after the migration is done.
