# Dataprep Migration Initiative — Executive Brief

> Copy-paste ready. Each "Slide" = one slide. Bullets are the on-slide text; _Talking points_
> are what you say. Replace anything in **[brackets]** with your specifics before presenting.

**One-line summary:** We are moving our ~100 Dataprep flows into our own maintainable,
cloud-native BigQuery assets — using an AI-assisted, repeatable process that proves each
migration is correct before anything goes live, and never touches production.

---

## Slide 1 — Title

**Dataprep Migration Initiative**
Moving our data pipelines to a maintainable, cloud-native foundation

[Your name] · [Team] · [Date]

---

## Slide 2 — The Situation

- We run **~100 prebuilt Dataprep flows**, organized into **Plans**, that clean and prepare our data.
- That logic lives **inside a GUI tool** — hard to version, review, cost-control, or maintain at scale.
- **Strategic risk:** dependence on a single visual platform whose long-term direction is uncertain.
- **Goal:** bring this logic into the stack we already own and trust — **BigQuery SQL and Python**.

_Talking point: This isn't just a tooling swap. It's about owning and being able to maintain
the logic that our reporting and analytics depend on._

---

## Slide 3 — What We're Building

- A **repeatable, AI-assisted migration toolkit** (built on Gemini CLI) that converts each
  Dataprep flow into clean, well-commented **BigQuery SQL or Python**.
- Not a one-off rewrite — a **standardized process** the team (and eventually each business unit) can run.
- **Built-in verification** proves every migrated flow matches Dataprep's output *before* it goes live.

_Talking point: The output isn't machine spew — it's organized, documented code a person can read,
maintain, and hand off._

---

## Slide 4 — Our Guiding Principles

- **Correct** — every migration is proven against the original, not assumed.
- **Safe** — production is never modified during the process.
- **Maintainable** — heavily commented, documented, version-controlled.
- **Repeatable** — the same guided process for all 100 flows.
- **Owned by us** — our stack, our code, no per-seat licensing.

---

## Slide 5 — How It Works (6 steps)

1. **Extract** — pull each flow's recipe from Dataprep (API or export).
2. **Translate** — convert it to commented SQL or Python (AI does the heavy lifting; we review).
3. **Stage safely** — output lands in an isolated, disposable area — *not* production.
4. **Verify** — compare the new output against live Dataprep output; require an **exact match**.
5. **Document** — auto-generate per-flow and per-Plan documentation.
6. **Cut over** — only after it passes verification and a human signs off.

_Talking point: Steps 3 and 4 are the heart of it — we can prove correctness without risk._

---

## Slide 6 — Safety: We Will Not Break Production

- **Production is read-only.** We never write to or alter existing tables.
- New output goes to a **disposable, isolated staging area** that self-cleans when we're done.
- Each migrated table is compared **value-for-value** against the live Dataprep output.
- **Nothing is promoted** without passing verification **and** a human sign-off.

_Talking point: The verification compares the same input through both engines — so any
difference is a logic difference we catch, not noise. This is the "foolproof" part._

---

## Slide 7 — Maintainability: Built to Be Owned, Not Just Run

- A plain-English **header on every flow**: what it does, why, and how to change it.
- **Per-flow and per-Plan READMEs**; the structure **mirrors Dataprep (Plans → flows)** so it's familiar.
- **Runs in the cloud** — maintainers edit SQL in a browser; **nothing to install**.
- **Version-controlled in Git** — full history, review, and rollback.

_Talking point: When someone needs to change a source file or tweak a step — the common
Dataprep edit — it's a one-line change in an obvious place, not a code hunt._

---

## Slide 8 — How It Helps the End User

- A **guided "golden path"** does the heavy lifting — users follow a repeatable, low-risk process.
- The safety net (automatic verification) means **non-experts can participate** without fear of breaking things.
- Path to **self-serve**: business units can eventually migrate and maintain their own flows.
- **We lead, train, and support** — the toolkit gets people productive fast.

---

## Slide 9 — Rollout Plan

| Phase | What happens | Rough time |
|---|---|---|
| **0 · Discovery** | Inventory all Plans & flows, map dependencies, rank, pick pilot | **[~X weeks]** |
| **1 · Pilot** | Prove the toolkit + verification on 3–5 representative flows | **[~X weeks]** |
| **2 · Scale** | Migrate the central backlog in dependency order | **[~X weeks]** |
| **3 · Enablement** | Train and hand off to business units, with guardrails | **[~X weeks]** |

_Talking point: We don't scale until the pilot proves correctness end-to-end. That keeps risk low._

---

## Slide 10 — What We Need

- **Access:** confirm Dataprep API/edition; ideally a **read-only role** on production data.
- **People/time:** **[X]** for the central effort.
- **Leadership endorsement** to engage business units in the enablement phase.
- **[Any budget/tooling asks]**

---

## Slide 11 — Why This Approach

| Option | Speed | Cost | Control | Built-in proof |
|---|---|---|---|---|
| Manual rewrite | Slow | High (labor) | High | None |
| Commercial migration tool | Fast | License $$ | Lower | Partial |
| **Our AI-assisted toolkit** | **Fast** | **No licensing** | **High** | **Yes (verification)** |

_Talking point: We get the speed of automation, the control of owning our code, and a built-in
correctness guarantee — without recurring license costs._

---

## Slide 12 — Risks & Mitigations

- **Correctness** → automated multi-tier parity check + human sign-off.
- **Complex / hard flows** → flagged early in discovery; handled by the central team, not LOB.
- **Access / edition limits** → confirmed in discovery; manual export fallback if needed.
- **Adoption** → training, the golden path, and generated docs lower the barrier.

---

## Slide 13 — Next Steps

- ✅ Approve the **pilot** (3–5 flows).
- ✅ Grant/confirm **data access**.
- ✅ Kick off **Phase 0 discovery**.
- 🎯 Review pilot results before committing to full scale.

_Call to action: With a green light on the pilot, we can show proven, verified results on real
flows within **[timeframe]** and a clear path to the full migration._

---

## Appendix A — Architecture at a glance (for the technically curious)

- **Extract:** Dataprep recipe → structured form (the logic is a finite set of steps, so this is
  reliable translation, not guesswork).
- **Target:** BigQuery SQL via **Dataform** (dependencies and run-order enforced automatically),
  or **Python** for the complex flows.
- **Verify:** input frozen → both engines run → schema / row-count / value-level comparison.
- **Orchestrate:** each **Plan** becomes a scheduled, ordered run — preserving today's behavior.

## Appendix B — What "done" looks like for one flow

Commented code + a passing parity report + auto-generated docs + a sign-off = the migration
record. Reversible, auditable, and ready to hand to whoever owns it.
