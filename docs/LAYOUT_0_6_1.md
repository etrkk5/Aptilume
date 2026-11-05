# Responsive layout verification — 0.6.1 historical record

On 5 November 2026, the question editor's native group selector, unbroken long strings, narrow report/survey filters and long employee-form period labels were corrected.

The check covered 320, 375, 640, 768, 1280 and 1440 pixel widths, light/dark themes, editor fields, catalog/team dialogs and publication confirmation. It included 118 geometry cases and five final viewport checks. Fixes used minimum-width constraints, wrapping and non-shrinking action icons. Table-local horizontal scrolling was distinguished from document overflow.

The 0.6.1 change did not alter business logic or dependencies. Its prebuilt Python package is historical and was removed from the current distribution in 0.8.0. Current brand, identity and EN/TR screens require their own verification, recorded in [VERIFICATION](VERIFICATION.md).
