# TroyHokanson.com

This is the canonical production repository for [TroyHokanson.com](https://TroyHokanson.com/).

## Repository consolidation

The earlier `troy-hokanson/portfolio` repository was reviewed as a near duplicate and was made private on August 29, 2026. Any remaining useful public-safe material must be reconciled here under these rules:

- preserve the established `Still Serving` visual direction and custom domain;
- retain the automated portfolio-health workflow and privacy contract;
- migrate verified investigative-practice and technical-training summaries;
- do not migrate raw evidence, case identifiers, subject information, credential numbers, stale résumé files, or unsupported totals;
- keep case-specific publication controlled by evidence review, sanitization and explicit public-release approval.

The earlier portfolio repository is not a production source and must remain private. It may be archived after any remaining public-safe material is reconciled. The separate `fraudinvbot` and `auditorsearchbot` repositories are independent applications and are not part of this website consolidation.

## Source-of-truth model

| Purpose | System |
| --- | --- |
| Public production site | This repository |
| Public evidence provenance | `evidence.html` with stable sanitized evidence IDs |
| Private supporting evidence | Restricted Google Drive evidence store |
| Command view and governance notes | Notion |
| Public-domain routing | `CNAME` → `TroyHokanson.com` |

## Validation

Pull requests run unit tests and a deterministic portfolio audit covering structure, local links, approved facts and privacy rules. Scheduled checks also compare the deployed pages with the production branch.
