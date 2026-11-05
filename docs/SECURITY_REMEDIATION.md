# Security remediation and organizational acceptance

The original review concerned 0.2.0 on 4 November 2026. The first remediation release was 0.3.0. This English summary preserves the findings and historical evidence while describing the current responsibility boundaries. Current test/build results belong in [VERIFICATION](VERIFICATION.md).

## Remediation record

| Finding | Implemented control |
| --- | --- |
| SEC-01 | Directory policy changes require HR approval after initial setup; proposals do not alter active policy. Corporate synchronization permanently closes initial setup privileges. |
| SEC-02 | HR controls LLM task activation. Production database movement is an explicit offline operations process. |
| SEC-03 | Connection profiles have typed allowlisted fields and encrypted secrets; changed destination/account requires secret re-entry. |
| SEC-04 | Unknown modes fail closed. Production is the image default and requires HTTPS, a persistent key, strong bootstrap password and verified PostgreSQL TLS. |
| SEC-05 | Atomic durable account/IP/global quotas, bounded password work, strong local passwords and bounded directory synchronization TTL. |
| SEC-06 | Destination host/port/network policy, DNS/IP pinning with TLS hostname verification, special-address blocks and no implicit HTTP proxy. |
| SEC-07 | Request/model body limits, job/export/mutation quotas, bounded output and session caps. |
| SEC-08 | Typed inputs, finite-number/schema validation and sanitized errors that do not echo submitted secrets. |
| SEC-09 | Fixed origin/host policy, ambiguous-cookie rejection, CSRF and protection headers on rejected requests. |
| SEC-10 | Atomic pending-only reviews, no self-review, evidence validation and immutable published results. |
| SEC-11 | Actor/correlation-aware JSON security events, authorized event visibility and retention cleanup. |
| SEC-12 | Export path/type/hash verification and retention; dev tools excluded from runtime; pinned image/action references. |
| SEC-13 | The earlier Debian runtime had 38 package-CVE matches across 13 CVEs (36 high, 2 critical). Runtime moved to pinned Alpine and removed pip/ensurepip tooling. Historical scans of both architectures reported no known findings at the recorded scan date, without ignore/VEX exceptions. |

The 0.3.0 verification recorded 119 passing tests, web build, dependency/static/image checks, native TLS tests and an isolated PostgreSQL flow using 42 competencies, 30 synthetic participants and three role profiles. It also checked CRUD-only runtime permissions and a dynamic UID/read-only-root container. Those historical results are not a claim that every later revision or future CVE is already verified.

## Current identity protections

Local accounts work without an external directory. HR manages business identities; integration administrators manage only administrator accounts. Admin cannot reset an HR/employee password, link themselves to an employee or grant a business role. Account changes use atomic revision checks, revoke sessions and prevent duplicate profile aliases, reporting cycles, self-lockout and removal of the last local privileged account. Provider-owned identities remain read-only locally.

Language selection does not alter authorization or stored response content. New assessment language is a validated EN/TR value pinned to the period; quoted evidence retains its original text.

## Organization acceptance checklist

| Owner | Required evidence |
| --- | --- |
| Identity / HR | Local-account ownership, role/profile/reporting links; if enabled, real directory CA, service account, HR groups, disabled users and manager-tree behavior. Validate policy approval and recovery access. |
| Secure access | An organization-managed MFA/conditional-access layer for privileged use and evidence that it cannot be bypassed. Direct local/directory password sign-in does not itself provide MFA. |
| OpenShift / network | HTTPS Route, fixed public origin, trusted proxies, SCC/dynamic UID, read-only root, writable data/tmp, ingress/egress controls and tested probes. |
| PKI / database | Real LLM/directory/PostgreSQL certificate and hostname checks; verify-full database TLS; separate migration/runtime roles. |
| Secrets / data | Persistent key and strong initial passwords in cluster Secret; access control, at-rest protection, backups, restoration and key-rotation/loss procedures. |
| Model / data owner | Real-provider calibration, evidence/quote and prompt-injection tests, approved destinations, DLP, retention and usage-cost policy. Connectivity does not establish model quality. |
| Operations / SOC | Collect secret-free structured events, configure and test alerts, and align retention. Defaults are 90-day audit and 7-day export retention. |
| QA / security | Target concurrency/load, reverse-proxy DAST, authorized penetration testing, failure/recovery drills and recurring dependency/image scans. |

## Operational notes

- Development `admin/admin` is rejected for production acceptance. Use strong runtime bootstrap values and an explicit account password-change process.
- Before production storage movement, back up and actually stop writers. `storage-migrate --profile-id ID --services-stopped` records the operator's assertion; it does not stop services itself.
- A Secret-provided first-install `DATABASE_URL` authorizes only that exact DB host/port when explicit DB network policy is absent. It does not authorize other panel destinations. Explicit restrictions take precedence.
- Multiple pods need a shared control store. Separate per-pod SQLite databases do not provide shared sessions or quotas; use PostgreSQL for replicated operation.
- Export retention does not delete independent backups or external copies. Organizations need their own retention policy for those.
- Pinned actions/images and vulnerability databases must be maintained. Source fixes and passing tests do not substitute for environment acceptance or guarantee zero vulnerabilities.
