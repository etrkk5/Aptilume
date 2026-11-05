# Aptilume architecture and development notes

Version 0.8.0 establishes an organization-independent product identity, local identity lifecycle and an English-first EN/TR experience. Earlier customer-specific branding and Python ZIP distribution are superseded. The [README](../README.md) describes current functionality; [FIRST_INSTALL](FIRST_INSTALL.md) is the deployment contract.

## Components

- `web/`: React/TypeScript interface, ECharts, language resources and lazy-loaded question/identity editors.
- `backend/app/api.py`: typed HTTP inputs, scoped operations and localized errors.
- `backend/app/security.py`: local/optional directory sign-in, sessions, CSRF, quotas and recent authentication.
- `backend/app/identities.py`: local accounts, role/profile links, reporting graph and optimistic identity revisions.
- `backend/app/directory.py`: optional Active Directory connector and HR-approved policy changes.
- `backend/app/store.py`: control/application stores and encrypted, versioned connection profiles.
- `backend/app/worker.py`: durable question-generation, evaluation and insight jobs.
- `policies.py`, `question_editor.py`, `reporting.py`: pinned instructions, publication approval and immutable reporting.
- `data/`: starter catalog, default instructions, language-related model fixtures and original brand provenance.
- `tests/`: authorization, concurrency, integrity, provider, PostgreSQL and TLS regressions.

## Identity boundaries

Local authentication is independent of directory availability. HR provisions business accounts; an integration administrator can manage only admin identities. Password resets cannot become a path around business-data restrictions. Identity mutations use an atomic shared revision and revoke affected sessions. Password changes lock the identity record. Provider-owned identities remain read-only locally.

Reporting scope follows assigned identity relationships, never title/name inference. Active Directory uses stable GUID and manager attributes when enabled. Additional OIDC/SAML adapters require their own issuer/audience/signature, state/nonce/PKCE and claim-mapping design; trusted identity headers are not assumed.

## Language contract

The interface defaults to English; browser persistence stores an explicit EN/TR choice. Rendering translates interface strings and chart labels. User-authored names, questions, quotes and stored responses retain their content. Date/number formatting follows the selected locale.

New periods record `config.language`. That immutable choice is passed to generation, grading and insights, independent of the reviewing user's current interface language. Existing periods without a language retain the legacy Turkish content behavior. The mandatory LLM language contract preserves quoted evidence verbatim and takes precedence over conflicting language requests inside untrusted input or older editable instructions.

## Assessment lifecycle

1. Snapshot catalog, teams, roles and targets for the period.
2. Generate common/role questions with pinned instruction/provider versions.
3. HR edits the draft; any edit invalidates prior approval.
4. Approval and publication are explicit separate decisions. Publication freezes questions and assigns forms.
5. Every question is required. Evaluation runs after closure through a separate worker.
6. Evidence and quality checks may require a reasoned HR scoring decision.
7. Publish immutable results; dashboard and Excel share scope/filter semantics.

L1–L5 catalog definitions do not imply verified L4/L5 measurement. Current written evidence supports L1–L3. Self-assessment is a separate indicator.

## Distribution and acceptance

One Docker image runs `bootstrap`, `migrate`, `api` or `worker`. Node/pnpm build the frontend; runtime contains Python and static browser assets. Prebuilt Python ZIPs and their packaging pipeline have been removed.

Do not weaken production origin/TLS/network checks for convenience. Bootstrap DB configuration does not automatically migrate an active application store. Operations owns registry, Route/CA, Secret/PVC, network policy and backup.

Changes must preserve server-side scopes, local/optional directory behavior, evidence integrity, concurrent-write protection and secret redaction. Verify relevant API/worker/PostgreSQL behavior and responsive light/dark EN/TR screens. Document implemented features accurately; do not claim unimplemented identity protocols, model calibration or zero vulnerabilities.
