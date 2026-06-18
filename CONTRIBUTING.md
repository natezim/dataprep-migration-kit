# Contributing — how we work this migration

The golden rule: **one flow at a time, end to end.** No bulk runs. This is what keeps a
100-flow migration reviewable and safe. Read this before you touch anything.

## The loop (per flow)

1. **`git pull`** — get the latest.
2. **`/dp:start`** in Gemini CLI — it shows progress and helps you pick the next flow (in
   dependency order). Finish anything `In progress` before starting something new.
3. **Branch** — `git checkout -b migrate/<plan>-<flow>` (one flow = one branch).
4. **`/dp:migrate context/<flow>`** — translate → compile/dry-run → parity-verify → document.
5. **Review the diff** — read what Gemini produced. The parity report must be green.
6. **Commit** — `git commit` (one flow per commit). Update `docs/catalog.json` status.
7. **Push / pull request (or merge request)** — when a GitHub or GitLab remote exists. Until
   then, just commit locally.
8. Back to step 2 for the next flow.

Never start a second flow until the current one is verified and committed.

## Where it lives

- **Version control: git.** It works with or without a server.
  - **No remote yet?** `git init` here and commit — you get full history and rollback today,
    on one machine. When a **GitHub or GitLab** remote is ready: `git remote add origin <url>`
    then `git push`. The history comes along and CI/Pages turn on. Zero rework — the repo
    already ships both a GitHub Actions workflow (`.github/workflows/pages.yml`) and a GitLab
    CI file (`.gitlab-ci.yml`); whichever host you pick activates, the other stays dormant.
  - **Do NOT** put this repo inside a OneDrive/SharePoint-synced folder — syncing `.git`
    corrupts it. Keep git as the project's home; share read-only artifacts separately.
- **Sharing read-only artifacts** (the dashboard, reports) before a remote exists: drop the
  generated files in SharePoint/Teams, or serve locally (below). People *consume* these; they
  don't edit them.

## Viewing the flow catalog

- **Hosted (preferred):** GitHub Pages or GitLab Pages serves `docs/catalog.html` automatically
  once the repo is on that host with Pages enabled — open the URL. (`catalog.json` is regenerated
  by the toolkit; CI only publishes it.)
- **Locally, before hosting:** the dashboard reads `docs/catalog.json`, which browsers block when
  you double-click the HTML. So from `docs/` run `python -m http.server`, then open
  `http://localhost:8000/catalog.html`.

## Keeping the workspace clean

- Everything has a home: SQL → `definitions/<plan>/<flow>/`, Python → `python/<plan>/<flow>/`,
  docs → `docs/` + `plans/<plan>/`, parity evidence → `output/parity/<plan>/<flow>.md`. Recipe
  inputs → `context/<plan>/<flow>/` (read-only).
- Scratch/throwaway → `output/temp/` only.
- Nothing at the repo root that isn't already here. `.gitignore` keeps secrets, raw exports,
  and temp out of git — check `git status` before committing so nothing unexpected slips in.

## Credentials — never commit them

- Dataprep PAT and any keys live in a local `.env` (gitignored). Copy `.env.example` to `.env`.
- Don't paste tokens into code, docs, commits, or chat.
