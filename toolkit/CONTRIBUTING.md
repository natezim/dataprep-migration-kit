# Contributing — how we work this migration

The golden rule: **one flow at a time, end to end.** No bulk runs. This is what keeps a
100-flow migration reviewable and safe. Read this before you touch anything.

## The loop (per flow)

1. **`git pull`** — get the latest.
2. **`/dp:start`** in Gemini CLI — it shows progress (from `status/migration_status.csv`) and
   helps you pick the next flow (in dependency order). Finish anything `In process` first.
3. **Branch** — `git checkout -b migrate/<plan>-<flow>` (one flow = one branch).
4. **`/dp:migrate <flow>`** — translate into one self-contained `<flow>.sql` → compile/dry-run →
   parity-verify → `@governance` review → write `validation.sql` + `EXPLANATION.md` + `parity.md`.
   Everything lands in `flows/<plan>/<flow>/`.
5. **Validate yourself** — read the governance report and `parity.md`, then **run
   `validation.sql`** to confirm new matches legacy. The parity audit must be green.
6. **Sign off** — when satisfied, run **`/dp:signoff <flow>`**: you attest you independently
   validated it, and the flow's status advances to **Productionized**. Status changes are
   gated — Gemini won't promote on its own.
7. **Commit** — `git commit` (one flow per commit). The status tracker updates.
8. **Push / pull request (or merge request)** — when a GitHub or GitLab remote exists. Until
   then, just commit locally.
9. Back to step 2 for the next flow.

Never start a second flow until the current one is verified, signed off, and committed.

## Where it lives

- **Version control: git.** It works with or without a server.
  - **No remote yet?** `git init` here and commit — you get full history and rollback today,
    on one machine. When a **GitHub or GitLab** remote is ready: `git remote add origin <url>`
    then `git push`. The history comes along. Zero rework.
  - **Do NOT** put this repo inside a OneDrive/SharePoint-synced folder — syncing `.git`
    corrupts it. Keep git as the project's home; share read-only artifacts separately.

## Viewing the status tracker

Open **`status/migration_status.xlsx`** in Excel (or `status/migration_status.csv` in any
viewer). It's a plain file the toolkit updates — no server, no hosting.

## Keeping the workspace clean

- **One folder per flow:** everything for a flow lives in `flows/<plan>/<flow>/` — `<flow>.sql`
  (primary), optional `<flow>.sqlx`, `validation.sql`, `EXPLANATION.md`, `parity.md`, and the
  read-only `recipe/`. Plan map → `flows/<plan>/README.md`. Cross-flow status tracking → `status/`.
- Nothing at the repo root that isn't already here. `.gitignore` keeps secrets, raw exports
  (`recipe/`), and temp out of git — check `git status` before committing so nothing unexpected
  slips in.

## Credentials — never commit them

- Dataprep PAT and any keys live in a local `.env` (gitignored). Copy `.env.example` to `.env`.
- Don't paste tokens into code, docs, commits, or chat.
