# Security review — historical 0.2.0 baseline

**Reviewed:** 4 November 2026. **Baseline:** `2aa16121c07a80de5f327280274eaf428c7b28ac` (0.2.0).

This is the original finding record, translated and summarized for the English-first documentation set. It describes the baseline before remediation, not the current open-issue status. See [remediation results](SECURITY_REMEDIATION.md) and [current verification](VERIFICATION.md).

The baseline was unsuitable for real employee production data: integration-administrator operations could indirectly bypass business-data restrictions. Review covered source, sessions/RBAC, directory trust, secrets, outbound LLM/DB requests, resource limits, exports, dependencies and container defaults. Evidence used temporary stores and synthetic records; no corporate target was attacked.

| ID | Severity | Baseline finding | Required remediation |
| --- | --- | --- | --- |
| SEC-01 | Critical | An integration admin could directly change HR directory-role policy and elevate their own access. | HR approval after initial identity setup; pending proposals must not alter active policy; bootstrap privilege must not reopen. |
| SEC-02 | High | An admin could copy 30 fixture employees into another DB and activate a self-created LLM destination. | HR-owned data-transfer bindings; controlled offline production database migration. |
| SEC-03 | High | Changing an endpoint carried the old secret to the new destination; unrestricted config fields could expose plaintext secrets. | Typed allowed fields, encrypted secret channel, secret re-entry after destination/account changes. |
| SEC-04 | High | A misspelled mode silently selected development; image defaulted to development; production accepted disabled PostgreSQL TLS. | Fail closed on unknown modes; production image default; fixed HTTPS origin and verified DB TLS. |
| SEC-05 | High | Account-wide brute-force protection was absent/non-atomic; each successful directory login triggered a full scan. | Durable atomic account/IP quotas, password-verification concurrency bounds, strong passwords and directory TTL. |
| SEC-06 | High | DNS validation and connection resolution were separate; proxy/mapped-address trust and DB/directory destination controls were incomplete. | Explicit destinations, verified-address pinning with SNI, metadata/loopback blocks and no implicit proxy. |
| SEC-07 | Medium | Oversized login bodies were accepted; LLM response, export and session resource use was insufficiently bounded. | Streaming limits, quotas, session caps and bounded model output. |
| SEC-08 | Medium | Untyped input dictionaries could cause 500s and reflect submitted values in validation errors. | Typed bounded inputs, consistent 4xx responses and secret-safe error serialization. |
| SEC-09 | Medium | Host/origin trust came from the request; an untrusted host could sign in. | Fixed production public origin, host/cookie ambiguity rejection and protection headers on errors. |
| SEC-10 | Medium | Review decisions lacked complete pending-only/concurrency/self-review guards. | Atomic pending-only decisions, self-review prevention and validated finite model output/evidence types. |
| SEC-11 | Medium | Central actor/correlation-aware security events were incomplete. | Structured secret-free events, authorized visibility and retention cleanup. |
| SEC-12 | Low | Download-time export integrity and retention were incomplete; dev tools and mutable image references remained. | File/hash/path validation, retention, minimal runtime and pinned references. |

The original 53 tests already covered several record scopes, IDOR, CSRF, logout and export restrictions; they did not cover all findings above. Dependency audits at that time reported no known package vulnerabilities, which did not establish application-logic safety. Existing React escaping, directory-filter escaping, verified directory TLS, encrypted service secrets and immutable published results were useful controls.

Remediation order was privilege separation, safe configuration/egress defaults, resource/input limits, review/audit/export integrity, then abuse regressions and image/PostgreSQL verification. Organization acceptance still requires real identity/network/PKI, privileged-access MFA, backup recovery, SIEM and authorized penetration/load tests.

References: [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).
