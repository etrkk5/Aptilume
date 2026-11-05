# First installation: local HR/admin and PostgreSQL

A clean organization workspace works without an external identity provider. Bootstrap creates `admin` and, when configured, `hr` using runtime Secret values. No sample employees or responses are loaded. Local users change their own password from the account menu.

## One runtime Secret

Name: **`aptilume-secrets`**. Type: **Opaque**. Use the [unfilled template](../deploy/openshift/secret.example.yaml).

| Key | Value |
| --- | --- |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial `admin` password. |
| `BOOTSTRAP_HR_PASSWORD` | Initial `hr` password. |
| `SECRET_ENCRYPTION_KEY` | Unique persistent Fernet key. |
| `DATABASE_URL` | PostgreSQL URL containing username, URL-encoded password, host and database. |

Passwords must be strong, 15–128 characters, without common/repeated patterns or the word `admin`. Use different passwords. Omitting the HR value preserves admin-only bootstrap; an explicitly empty/invalid HR value blocks new-account initialization. Passwords are hashed with Argon2 and are not embedded in the image. Operators choose the initial passwords, so pod access is not needed to discover them.

Generate the encryption key once in the project's Python environment:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`DATABASE_URL` initializes control and application tables in the same PostgreSQL database on an empty installation. The database must exist and the installation role must have schema permissions. It does not create a local application SQLite store in this configuration. `CONTROL_STORE_URL` takes precedence for the control store if a separate database is needed. Percent-encode reserved characters in URL credentials.

## Operations checklist

1. Build `aptilume:0.8.0` and push it to the organization registry. Do not pass secrets during build.
2. Put Secret and workloads in the same OpenShift project. Expose the Secret as environment variables to bootstrap, API and worker.
3. Set `APP_MODE=production` and `PUBLIC_BASE_URL=https://YOUR_ROUTE_HOST`. Mount the PostgreSQL CA at the URL's `sslrootcert` path. Provide shared writable `/app/data` and writable `/tmp`.
4. Run the same image with the `bootstrap` argument and wait for success. It prepares tables, default instructions, the starter catalog and initial accounts.
5. Start separate `api` and `worker` containers/pods. The entrypoint is already `python -m app.cli`; change only its argument. The API listens on port `8080`. Worker has no HTTP listener; do not apply API HTTP probes to it.
6. Create Service/HTTPS Route and sign in with the configured accounts. Admin configures a real LLM connection; HR activates the task bindings. Production does not run mock model tasks.

Container environment reference:

```yaml
envFrom:
  - secretRef:
      name: aptilume-secrets
```

A Secret-provided bootstrap `DATABASE_URL` authorizes only its exact database host/port when no explicit DB host/CIDR policy is supplied. Certificate verification, IP pinning and metadata/special-address blocks remain enforced. Explicit `DB_ALLOWED_HOSTS` or `OUTBOUND_ALLOWED_CIDRS` override this convenience default and must completely describe the permitted DB destination. Configure additional directory/LLM destinations separately. See the [production guide](../README.md#openshift--production-installation).

## Users, roles and language

Sign in as HR. Create teams, role profiles and employees in **Teams and targets**. Then use **Identity and access → Create account** to link employee/manager accounts to profiles. Select a local manager to establish reporting scope. Names, titles and shared department names do not grant access.

HR manages business identities. Integration administrators manage only administrator accounts; they cannot reset HR/employee passwords. Identity edits revoke affected sessions. Duplicate active profile links, cycles, self-lockout and removal of the last active local privileged identity are blocked. Sensitive writes require recent sign-in.

English is the first-run interface default. EN/TR is remembered in the browser. New assessment periods retain the selected language for generation, evaluation explanations and insights. Switching language does not rewrite existing content.

Active Directory is an optional connector. OIDC/SAML connectors are not included. Validate corporate identities before planning local-account retirement; the last local privileged-account protection remains active.

## Restart and upgrade behavior

Preserve DB, Secret and shared data. Restart/bootstrap does not reset passwords, roles, inactive accounts or assessments. `BOOTSTRAP_*` is used only when the corresponding account is missing. Changing the Secret does not reset an existing password.

`DATABASE_URL` prepares the initial application binding. Later changes do not silently migrate or replace the active profile. Update an existing application profile's password when database credentials rotate; use controlled offline migration for a destination change.

For upgrades, stop writers and run `migrate` before bootstrap/restart. Operations owns deployment, certificates, storage, network policy, backup and recovery.
