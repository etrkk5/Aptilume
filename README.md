![Aptilume — Make AI capability measurable](docs/images/aptilume-hero.svg)

# Aptilume

**AI Skills Intelligence · Measure capability. Illuminate potential.**

Aptilume helps organizations understand their AI capabilities and turn assessment evidence into focused development investment. It brings role-aware surveys, human approval, asynchronous AI evaluation and visual reporting into one workspace.

HR sees organizational development needs. Managers focus on their reporting teams. Employees follow their own assessments and development plans. An independent product identity, local account management and configurable model connections make Aptilume adaptable to different organizations.

## From AI investment to development priorities

- **Measure in context.** Team objectives, duties, tools, role titles and target competencies inform question generation. Shared questions support comparisons; role questions reflect actual work.
- **Keep people in control.** HR adds, edits, removes and saves AI-generated questions before approving and publishing a set.
- **Evaluate evidence.** Open-ended responses are assessed against rubrics and references after the period closes. Written performance, knowledge checks and self-assessment remain distinct indicators.
- **Make development actionable.** Dashboards, competency maps, target gaps, participation, response-quality reviews and development plans use the same published result version.
- **Retain accountability.** Versioned policies, catalog snapshots, connection profiles, approvals and audit events make important decisions traceable.

## Inside Aptilume

### See capability across the organization

Participation, shared written evidence and target coverage come together in a filterable dashboard. Teams get a clear view of development priorities while access scope stays enforced.

![English competency dashboard with participation and target coverage](docs/images/dashboard-en.png)

Compare teams, explore score distributions and inspect evidence coverage.

![Team comparison, participation and competency-level charts](docs/images/analytics-en.png)

### Let AI prepare. Let HR decide.

Review generated questions, refine rubrics and references, and publish only after explicit approval.

![HR question editor with an English draft and publication controls](docs/images/question-editor-en.png)

### Start independently. Add integrations when needed.

Local identities, role boundaries and reporting relationships support organization-specific access without a mandatory directory service.

![Local identity management in Aptilume](docs/images/identity-en.png)

*Screenshots use synthetic demonstration data and mock scores. They illustrate product behavior, not real employee results or measured model quality.*

## Assessment workflow

1. HR defines the competency catalog, teams, role profiles and target levels.
2. Employee profiles are linked to sign-in accounts and reporting relationships.
3. Create a period for selected teams or **All teams**. The current EN/TR selection determines its content language.
4. AI prepares questions. HR reviews, edits, saves, approves and publishes the set.
5. Employees complete every required question; drafts are saved automatically.
6. After closure, a separate worker evaluates responses. Off-topic, nonsensical and other review-required answers enter the HR queue.
7. HR publishes results. Authorized users explore filtered reports, export Excel and track development actions.

```mermaid
flowchart LR
    C[Team context & targets] --> G[AI question draft]
    G --> H[HR review & approval]
    H --> S[Published survey]
    S -->|Period closes| E[Batch evaluation]
    E -->|HR publishes| R[Insights & development]
    classDef stage fill:#edf5ff,stroke:#3e87c6,color:#163b62
    classDef human fill:#e4f8f6,stroke:#259b9a,color:#154f55
    class C,G,S,E stage
    class H,R human
```

## Product capabilities

| Area | Capabilities |
| --- | --- |
| Competency catalog | A 42-competency starter catalog; create, edit, archive and restore; L1–L5 definitions. |
| Team and role context | Tasks, tools, constraints, role/title profiles, job bands and target competencies. |
| Surveys and question editor | Open responses, single-choice questions and self-assessments; editable options, references and rubrics; approval before publication. |
| Assessment policy | HR edits generation and evaluation instructions in one screen; defaults and immutable policy versions are retained. |
| Evaluation jobs | Durable background work, retries, failure visibility, evidence validation, human review and publication. |
| Analytics | Team, role/title, competency, section, job-band and response-status filters; heatmaps, participation and target-gap views. |
| Reporting | Scope-aware Excel exports, published result versions, comparisons and development plans. |
| Integrations | Add, edit, test and remove LLM/database profiles; select active profiles for individual tasks. |
| Identity management | Local accounts, roles, profile links, reporting relationships, password changes, account deactivation and session revocation. |
| Experience | Original Aptilume vector mark, responsive light/dark themes and persistent EN/TR selection. English is the first-run default. |

**Measurement boundaries:** The catalog supports L1–L5 definitions. The current written-evidence approach supports L1–L3; it does not present L4/L5 as automatically verified proficiency. Written scores, knowledge checks and self-reports are not collapsed into a single ability score. Aggregate scores with fewer than five valid people are suppressed. Technical model failures or missing evidence are not zero ability scores. Real-model quality requires organizational calibration.

**Language:** EN/TR controls interface labels, filters, messages and chart labels. New periods retain the selected language for question generation, evaluation explanations and insights. Existing questions, employee responses, imported catalog content and historical records keep their authored language. Switching the interface language does not rewrite stored content. Excel headings follow the language selected when the export is queued; original responses remain unchanged.

## Identity and access

**Local username/password authentication works independently.** Initial `admin` and `hr` passwords come from a runtime Secret. In **Identity and access**, HR provisions employee/manager accounts and links them to employee profiles and reporting relationships. Local users change their own password from the account menu.

| Role | Scope |
| --- | --- |
| HR (`hr`) | All business data, catalog/policy, business account and profile mappings, question approval, reviews and publication. |
| Manager (`manager`) | Their assigned reporting tree and own profile; unrelated employees and teams are excluded. |
| Employee (`employee`) | Their own profile, surveys, results and development plans. |
| Integration administrator (`admin`) | Connections and integration-administrator accounts; no employee assessment data or business-account password control. |

An integration administrator cannot gain business access by resetting an HR/employee password. HR manages business identities. Duplicate active profile links, reporting cycles, self-lockout and removal of the last active local privileged account are blocked. Identity edits revoke affected sessions and use revision checks to prevent lost updates.

The existing **Active Directory connector is optional**. It uses certificate-verified LDAPS/StartTLS, group mapping and the `manager` relationship. Local sign-in does not depend on it. Ready-made OIDC/SAML connectors are not included in this release; identity headers from a reverse proxy are not implicitly trusted.

## Technical architecture

| Layer | Technology and responsibility |
| --- | --- |
| Web | React 19, TypeScript, Vite and ECharts; static assets after build. |
| API | Python 3.12+, FastAPI; sessions, authorization, scope checks and business rules. |
| Worker | Separate Python process; durable jobs for generation, evaluation and insights. |
| Persistence | SQLAlchemy/Alembic; PostgreSQL for organization deployments, SQLite for local development. |
| Control store | Accounts, sessions, connection versions, policies, task bindings and encrypted secrets. |
| Application store | Teams, profiles, periods, questions, responses, results and export records. |
| Distribution | Multi-stage Docker image; no Node.js or frontend build tools in the runtime. |

For an empty installation, `DATABASE_URL` initializes both stores in the same PostgreSQL database. Use `CONTROL_STORE_URL` when a separate control database is needed. Application connection profiles are managed in the panel; moving existing data requires the controlled offline migration process.

LLM adapters support OpenAI-compatible Chat Completions and Responses formats. Choose the adapter supported by your gateway. The application validates JSON structure, rubric bounds and quoted evidence. Supply your approved endpoint, model, key and trusted CA/host configuration. The `mock` provider is for development/presentation only; production model tasks require a real provider.

## Quick local installation — Docker

Prerequisites: Git, Docker and Docker Compose.

```bash
git clone https://github.com/etrkk5/Aptilume.git
cd Aptilume
cp .env.example .env
```

Keep `APP_MODE=development` for local use. Uncomment `BOOTSTRAP_HR_PASSWORD` and set a unique strong password to enable HR sign-in. `admin/admin` is a local-development default only.

```bash
docker build -t aptilume:0.8.0 .
docker compose -f compose.dev.yml up -d --no-build
```

Open **http://127.0.0.1:8080**. Bootstrap prepares the catalog, default instructions, `admin`, and `hr` when configured; it does not load sample employees. Sign in as `hr`, create team/role/employee profiles, then provision their accounts in **Identity and access**.

Stop with `docker compose -f compose.dev.yml down`. Preserve the volume to keep data. For an isolated workspace with sample records, set `APP_MODE=demo` and follow the [presentation guide](docs/DEMO.md).

## Development from source

Requires Python 3.12+, Node.js 22+ and pnpm 11.25. Node.js builds the interface; API and worker run in Python.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
corepack enable
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
export APP_MODE=development
export PYTHONPATH=backend
export BOOTSTRAP_HR_PASSWORD='REPLACE_WITH_A_UNIQUE_STRONG_PASSWORD'
python -m app.cli bootstrap
python -m app.cli api
```

In another terminal, activate the same environment, set `APP_MODE=development` and `PYTHONPATH=backend`, and run `python -m app.cli worker`. The API uses port `8080` by default. Prebuilt Python ZIP distribution has been removed; install from source or build the container image.

## OpenShift / production installation

**Image build and first installation are separate.** Credentials, database URLs and encryption keys are runtime configuration. See the [first-install guide](docs/FIRST_INSTALL.md) and [unfilled Secret template](deploy/openshift/secret.example.yaml).

1. Build the image and push it to your registry. For both supported architectures, use `docker buildx build --platform linux/amd64,linux/arm64 ...`.
2. In the application's OpenShift project, create an Opaque Secret named `aptilume-secrets`. Expose its keys as environment variables to bootstrap, API and worker:

| Secret key | Value |
| --- | --- |
| `BOOTSTRAP_ADMIN_PASSWORD` | Unique strong 15–128 character password for the initial `admin`. |
| `BOOTSTRAP_HR_PASSWORD` | Strong initial `hr` password; provide it for local business administration. |
| `SECRET_ENCRYPTION_KEY` | Unique, persistent Fernet key. |
| `DATABASE_URL` | `postgresql+psycopg://USER:URL_ENCODED_PASSWORD@HOST:5432/DB?sslmode=verify-full&sslrootcert=/etc/certs/ca.crt` |

3. Set `APP_MODE=production` and `PUBLIC_BASE_URL=https://YOUR_ROUTE_HOST`. Mount the PostgreSQL CA at the URL's certificate path. The database must already exist and the installation role must be able to create tables.
4. Provide writable `/app/data`, shared by API and worker, and writable `/tmp`. On first installation, run the same image with **`bootstrap`** and wait for success.
5. Start **`api`** and **`worker`** in separate containers/pods. The image entrypoint is already `python -m app.cli`. The API Service targets **8080**; expose it through an **HTTPS Route**.
6. Sign in with `admin`/`hr` and the supplied passwords. Configure and test a real LLM profile; HR activates task bindings. Directory integration is optional.

Generate the encryption key once in the project's Python environment:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Preserve the database and key across deployments. Bootstrap values do not reset existing passwords. Changing `DATABASE_URL` does not automatically migrate the active application database.

**Runtime:** The image supports non-root execution, arbitrary OpenShift UID/group 0, a read-only root filesystem and dropped capabilities. API and worker run separately. Worker has no HTTP listener, so do not attach API HTTP probes to it. SQLite requires a single API/worker pair and suitable shared storage; replicas/HA require PostgreSQL and target-load verification.

**Network:** A bootstrap `DATABASE_URL` authorizes only its exact database host/port. TLS verification, DNS/IP pinning and metadata/special-address blocks remain active. Explicit `DB_ALLOWED_HOSTS`/`OUTBOUND_ALLOWED_CIDRS` take precedence. Operations must configure host/CIDR and CA settings for additional database, directory and LLM destinations. Restrict `FORWARDED_ALLOW_IPS` to actual trusted proxies; do not use `*`.

| Health endpoint | Purpose |
| --- | --- |
| `/health/live` | API process. |
| `/health/ready`, `/health/startup` | Control store and recovery service. |
| `/health/application` | Application database/schema. |

Upgrade sequence: **backup → stop API/worker and writes → `migrate` → `bootstrap` → API + worker**. Separate migration/runtime database roles according to organizational policy. Operations owns Deployments, Services, Routes, PVCs, NetworkPolicies and registry publication; the repository does not deploy itself.

## Security and verification

Passwords use Argon2 hashes. Connection secrets use a persistent Fernet key. Production enforces HTTPS, Secure/HttpOnly session cookies, CSRF/origin checks, resource limits, server-side authorization and recent authentication for sensitive writes. Evaluation/policy versions, publication hashes and audit events are retained.

```bash
python -m pytest
pnpm --dir web build
bandit -r backend/app -ll -ii
```

GitHub Actions runs tests, dependency audits, web/image builds, container vulnerability scans and isolated PostgreSQL scenarios. See the [verification record](docs/VERIFICATION.md). Real identity/LLM services, MFA/access gateways, organizational PKI/network, load/penetration testing and backup recovery need environment-specific acceptance. Passing tests do not establish a zero-vulnerability guarantee.

## Documentation

- [First installation](docs/FIRST_INSTALL.md)
- [Architecture and development notes](docs/DEVELOPMENT_PLAN.md)
- [Question editing and publication](docs/FEATURES_0_6.md)
- [Catalog management](docs/FEATURES_0_5.md)
- [Policies, quality reviews and reporting](docs/FEATURES_0_4.md)
- [Security findings and operational responsibilities](docs/SECURITY_REMEDIATION.md)

The original Aptilume mark is an editable SVG created for this project. Asset provenance and checksum: [brand-source.json](data/brand-source.json).
