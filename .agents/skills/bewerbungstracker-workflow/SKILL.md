---
name: bewerbungstracker-workflow
description: Use when changing, reviewing, deploying, or debugging Bewerbungstracker; covers privacy-sensitive email/CV handling, services-vs-api architecture, async worker/env pitfalls, Docker deploy discipline, master branch workflow, and verification.
---

# Bewerbungstracker Workflow

Use this skill for application, email, CV/PDF, async task, Anthropic-cost, Docker deploy, or production debugging work in Bewerbungstracker.

## Core Rules

- Default branch is `master`, not `main`.
- Keep business logic in `services/`; `api/` routes stay thin.
- Use `services/job_matching/claude_utils.py::_get_anthropic_client` as the Anthropic client source of truth.
- Email parsing must keep signature/footer stripping before keyword matching.
- This is privacy-sensitive software. Do not log raw CVs, email bodies, application contents, tokens, or secrets.
- Long-running work goes through `services/tasks/handlers/`; do not block Flask requests for more than about one second.
- Worker container must mount the same `.env` as the app. Otherwise it can poll a different SQLite DB and tasks remain queued.
- Do not leave persistent hotfixes in running containers. Commit, build with `deploy/container/build.sh`, then recreate through `deploy/container/setup-oracle-vm.sh`.
- Handoffs go in `CHANGELOG.md`, not `AGENTS.md`.
- **All browser JS libraries are vendored locally in `components/vendor/`.** Never add new CDN `<script>` tags to `index.html`. Vendor the library instead. This avoids CSP + Service Worker MIME-type conflicts that have broken PDF export twice (2026-07-03).
- **When adding a new browser library:** download it to `components/vendor/`, reference it via `/components/vendor/...` in `index.html`, and update CSP in `app.py` if needed. Verify `tests/test_security_headers.py` passes.
- **Service Worker note:** `service-worker.js` intercepts all GET requests including cross-origin ones matching static asset extensions (`.js`, `.css`). Vendoring eliminates MIME-type mismatches from cached CDN responses.

## Verification

For normal code changes:

```bash
pytest tests/
```

For IMAP, email cron, Anthropic API, CV upload, or production changes, state explicitly whether verification used real credentials/data or mocks only. For deploys, verify app and worker DB env paths, container health, and running image/source traceability. For vendor asset changes, verify `window.jspdf` is defined in browser console (F12 → `typeof window.jspdf`).

## Read Before Acting

- `AGENTS.md` for hard rules.
- `CHANGELOG.md` for handoffs.
- `deploy/container/build.sh` and `deploy/container/setup-oracle-vm.sh` before production container work.
