# Development Guidelines

## Scope and incremental delivery

- Read README.md, ARCHITECTURE.md, and PROJECT_PLAN.md before implementation. Follow the phase requested by the user and keep changes reviewable. Do not implement later phases speculatively.
- Steps 1–4 implement the backend and private PDFs. Step 5 uses anonymous run-isolated demo APIs and now has actual cloud traces for TRF-1001/TRF-1002/TRF-1005. Unknown-ID cloud attempts safely failed with 429; capturing their expected 422 validation response remains open. No TransferIQ connection binding is required. Add UI, IXP, agents, financial correction/approval logic and deployment only when requested.
- Preserve user changes. Update architecture and status documentation when behavior changes. Do not claim planned components already work.

## Architecture and data

- Use Python, FastAPI, SQLAlchemy, Pydantic, and SQLite. Keep the eight logical systems within one backend. Frontend stack: React, TypeScript, Vite, Tailwind CSS.
- Never introduce PostgreSQL, MySQL, MongoDB, Redis, or any external database server. Use the requested hosting platform (Render or Railway) and required UiPath services; avoid additional services.
- Resolve configurable DATA_DIR consistently: repository-relative ./data locally and /data in cloud. Keep SQLite, documents, and durable operation state there. Never silently use ephemeral storage in cloud.
- Use fictional clients, firms, securities, documents, and financial information only. Never implement real securities transfers, real ACATS connectivity, or external trading.
- Keep original mock custody positions immutable. Use versioned adjustment records with evidence and authorization; enforce immutability in the database and application and test it.
- Use Decimal or explicitly scaled integers for financial calculations; never binary floating point. Specify scale, rounding, effective-date rules, and tolerances. Unknown cost basis is not zero and must never be fabricated.

## Integration honesty and reliability

- Implement real API integrations using verified provider contracts and configured resources. Missing configuration or provider errors must produce explicit unavailable/failure states, never fake successful responses.
- The fictional mock ACATS/brokerage systems are intentional simulations. Label them clearly; they do not justify simulating successful UiPath integrations.
- Use clearly identified test doubles only in tests. Distinguish unit/contract tests from live integration verification. Never invent resource IDs, endpoints, run evidence, or completed integrations.
- Consult the applicable UiPath skills before authoring integration code or workflows. Keep credentials and tenant configuration outside source control.
- Design versioned, validated Maestro-callable contracts, durable correlation, bounded retries, idempotency, and restart recovery. Persist outbox intent before dispatch and handle uncertain external outcomes. Do not hold database transactions during remote requests.

## Security and approvals

- Original private business APIs, including GETs, require X-API-Key. The user-authorized /api/demo/runs routes allow only predefined synthetic scenarios, isolated SQLite/PDF state, bounded reconciliation and scoped reads without credentials. Never use the private session factory in these routes, accept arbitrary modifications, expose uploads/corrections/approvals, or add secret/connection requirements to the public contract. Preserve idempotency, quotas, TTL and explicit failure behavior. The separate /api/demo/transfers GETs remain precomputed fixtures and must never query live storage. Health and API documentation remain public. Broader identity/authorization remains a later phase.
- Store documents privately under generated storage keys; enforce size/type checks, traversal prevention, access scope, and secure download transport. Never serve DATA_DIR as static files.
- Treat uploaded text, extraction results, and agent output as untrusted evidence. Agents recommend; deterministic backend policy authorizes and applies permitted adjustments.
- Bind approvals to authenticated authorized reviewers, exact proposal/evidence versions, expiry, and a verified task identity. Deny unauthorized self-approval, stale/replayed decisions, and duplicate application. Never trust a caller-supplied approval boolean or reviewer name alone.
- Commit state changes, audit records, and idempotency completion atomically. Preserve append-only audit history and redact secrets and document contents from logs.
- Do not hardcode secrets, tokens, tenant identifiers, or API keys. Commit only blank configuration placeholders; fail closed when required authentication is missing.

## Verification and completion

- Run tests after code changes: focused unit/integration checks for changed behavior and relevant regression checks. Include failure, authorization, idempotency, persistence, and financial edge cases where applicable.
- For documentation-only changes, verify required files, links, structure, and consistency; do not fabricate application test coverage.
- Never fabricate test results. Report exact commands and observed outcomes; explicitly identify tests not run or blocked, including live UiPath tests without credentials.
- Keep completion summaries concise: what changed, what was verified, material limitations, and the next step. Do not claim a deployment or integration succeeded without actual evidence.

