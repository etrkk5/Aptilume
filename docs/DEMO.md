# Presentation workspace

Set `APP_MODE=demo` in the local `.env`, build the current image and run:

```bash
docker build -t aptilume:0.8.0 .
docker compose -f compose.dev.yml up -d --no-build
docker compose -f compose.dev.yml exec -T api python -m app.cli demo-accounts
```

Open http://127.0.0.1:8080. Demo creates an isolated `DATA_DIR/presentation-demo` store, a local key, mock provider, four role accounts and synthetic assessment data. It does not inherit production `CONTROL_STORE_URL`, `DATABASE_URL` or `SECRET_ENCRYPTION_KEY`. Repeated bootstrap preserves accounts, passwords and edits. Credentials are random and shown only by the explicit operations command, not the web API or startup logs.

| Account | Scope |
| --- | --- |
| `hr` | Organization-wide business and integration views. |
| `manager` | Assigned Data & Analytics reporting tree. |
| `employee` | Their own profile, forms and results. |
| `admin` | Integration configuration only. |

These are regular scoped sessions. Existing presentation identities are read-only in identity management. New organization accounts are provisioned in development/production local identity stores. The bootstrap `admin/admin` development password does not apply to demo accounts.

## Suggested walkthrough

1. HR: dashboard, team/competency filters, participation, result information and scoped Excel.
2. HR: a draft question set; edit/add/remove questions, save, approve and publish. Publication assigns forms and locks question content.
3. Manager: their reporting scope and development actions.
4. Employee: own profile and required questions; draft autosave and explicit submission.
5. HR: close a period, start background evaluation, inspect quality cases, record a reasoned decision and publish results.
6. Admin: model/database profiles and optional directory connector. Real corporate credentials are not needed for the mock walkthrough.
7. EN/TR and light/dark controls: interface language can change while existing data retains its authored language. New periods use the selected language.

Mock scores are deterministic synthetic fixtures and do not establish real-model accuracy. The product has one original Aptilume brand. Presentation data is identified where needed for interpreting reports.

## Production transition

`APP_MODE=production` selects the organization store and rejects demo identities/data and mock model execution. Restart all processes after changing mode. Provide real HTTPS/CA, persistent secrets, PostgreSQL, permitted destinations and an approved LLM profile as described in [FIRST_INSTALL](FIRST_INSTALL.md). Local accounts work without directory integration. Real organizational acceptance remains separate from a successful presentation.
