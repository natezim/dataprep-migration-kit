# Governance — readiness, status gating, and signoff

The team owns the migration. Governance exists so a flow is genuinely ready before a human signs
it off — and so humans (not Gemini) carry responsibility. `@governance` runs the checklist;
`/dp:signoff` enforces the human attestation.

## The status lifecycle (gated)

`status/migration_status.csv` (+ generated `.xlsx`) tracks every flow against the total inventory:

**Not started → In process → Validating → Parallel runs → Productionized**

- **Not started** — inventoried, not yet begun.
- **In process** — being translated.
- **Validating** — parity audit running / under review.
- **Parallel runs** — new + legacy running side-by-side over the agreed validation window.
- **Productionized** — signed off; the new pipeline is the source of truth.

**Status changes are gated.** Gemini asks the user to confirm before advancing a flow's status —
never auto-advances. Advancing into Validating / Parallel runs / Productionized always prompts.

## The readiness checklist (`@governance`)

1. Single self-contained `.sql` (Create-Execute-Clean; no temp tables left behind).
2. No hard-coded values (dates/params are variables).
3. Comments — header + inline per CTE; no `SELECT *` in joins.
4. Parity green (Strict mode, frozen input, 4-tier) or every diff documented.
5. `validation.sql` + `EXPLANATION.md` present and clear.
6. Naming + safety (`EXT_`/`STG_`, staging-only writes, Dataprep/prod read-only, ≤60-char names).
7. Status consistent; not Productionized except via signoff.

Result is `flows/<plan>/<flow>/governance.md`: READY or NOT READY + blockers.

## Why human signoff (the ownership gate)

Users are responsible for these pipelines **regardless of how they were built**. "Gemini built
it" is not validation. `/dp:signoff` requires the user to attest, explicitly, that they:
- independently **reviewed** the SQL themselves, and
- ran their **own** validation (e.g. `validation.sql`) and accept the result.

Only then does status become **Productionized**, recording `signed_off_by` + `signed_off_date`.
Gemini never self-promotes. No rubber-stamping.
