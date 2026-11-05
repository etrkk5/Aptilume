# Verification record

## 0.8.0 — independent product, local identity lifecycle and EN/TR

Verified on 5 November 2026 with synthetic data and isolated services. No organizational deployment was performed.

- **235 Python tests passed**, with three existing dependency deprecation warnings. Local identity boundaries, atomic edits, reporting scopes, required responses, quality gates and period-pinned language are covered. English/Turkish Excel headings are queued with the export; response content is preserved.
- **The frontend language regression passed**: English first-run default, persistent Turkish selection, dynamic/interpolated labels, locale formatting, unchanged chart inputs and translated chart output. TypeScript/Vite production build passed; the main bundle remains below the 500 kB warning threshold.
- **Bandit reported no medium/high findings**; three reviewed low-level findings remain. Dependencies were not added for localization.
- **Both amd64/arm64 container images built successfully.** Frontend compilation uses the build platform and caches package metadata/store while preserving frozen-lockfile and supply-chain checks. A transient registry timeout was resolved by retrying with persistent build caches.
- **PostgreSQL 16 integration passed**, including local HR/admin bootstrap, generic local admin login, admin-only identity listing, business-role escalation rejection, revision conflicts, CRUD-only runtime, assessment/question publication and scoped exports.
- **Production PostgreSQL TLS passed** on a separate clean database and isolated CA: both stores reported encrypted connections, local HR/admin logged in without directory integration, admin was denied business data, and Secure `__Host-` sessions were verified.
- **Real browser checks passed** at 320, 375, 768 and 1440 pixel widths. Identity forms fit their viewport; wide identity tables scroll inside their own container. EN/TR switching preserves active form state and persists across reload. Light/dark themes and English-generated questions/references were inspected.
- The original SVG logo and README cover were validated. README screenshots were captured from the real interface using synthetic English demonstration records. Local documentation links and the logo checksum were checked. Python ZIPs, their launcher/builder/tests and the packaging CI step were removed.

## 0.7.0 — first organization installation, 5 November 2026

- **226 Python tests passed**. Local HR/admin bootstrap, separate scopes, password/session behavior, invalid configuration and idempotent initialization were verified.
- A single Secret URL initialized both stores in PostgreSQL; the initial application-profile password was encrypted. Restart did not overwrite active profiles or credentials.
- Native PostgreSQL TLS was enabled with an isolated CA. In production mode, both stores reported encrypted connections, HR/admin signed in without a directory, admin was denied business access, and Secure `__Host-` sessions worked. No corporate service was contacted.
- amd64/arm64 images and prebuilt UI file parity were checked. The Python ZIP distributed at that time has been removed in 0.8.0.

## Earlier history

| Version | Recorded verification |
| --- | --- |
| 0.6.1 | Responsive editor/filter/survey fixes; 118 geometry cases and five final viewport checks across light/dark themes and 320–1440 px widths. No business-logic change. |
| 0.6.0 | **209 tests passed**; HR question CRUD, shared-block edits, approval invalidation, version races, publication freeze, variable question counts and scoring denominators; PostgreSQL CRUD-only editing/publication; browser checks. |
| 0.5.0 catalog | **186 tests passed**, followed by 47 affected regressions after a PostgreSQL query adjustment. Catalog CRUD/archive/restore and immutable snapshots were checked. |
| 0.5.0 local package | Historical Python-only ZIP setup, four-role scopes, manifest/file integrity and UI parity were checked. The packaging pipeline is no longer shipped. |
| 0.4.0 | **169 tests passed**; HR policy versions, required answers, quality review decisions, filtered reporting/Excel and PostgreSQL behavior. |
| 0.3.1 | **131 tests passed**; isolated presentation mode, credential creation/preservation and rejection of demo data/sessions in production. |
| 0.3.0 | **119 tests passed**; security remediation, native TLS, PostgreSQL, dynamic UID/read-only-root runtime, dependency/static/image audits and browser policy approval. |

These entries record results at their source revision and scan date. Real corporate CA/identity/model endpoints, MFA/access gateways, OpenShift networking, target load, penetration testing and backup recovery still require environment-specific acceptance. See [security remediation](SECURITY_REMEDIATION.md).
