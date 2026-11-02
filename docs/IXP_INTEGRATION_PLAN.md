# Future UiPath IXP document handoff

This is a planned integration contract only. Step 4 implements the backend document service; no Maestro Flow, IXP project/model, file-output activity, extraction call, or agent integration has been created or verified.

## Backend contract available now

1. Receive a `transferId` from the orchestrating process.
2. With the service key in an `X-API-Key` header, call `GET /api/transfers/{transferId}/documents?documentType=ACCOUNT_STATEMENT`. Follow `limit`/`offset` pagination when needed.
3. Select the intended `documentId` and version from READY metadata. Evaluation-only variants are excluded by default; use `includeEvaluation=true` only for explicit model-evaluation work. Do not choose an arbitrary first document when several versions/sources exist.
4. Download through `GET /api/transfers/{transferId}/documents/{documentId}/download`, sending the same authentication header. The scoped route verifies ownership.
5. Treat the response as PDF bytes. Check MIME type, size, and SHA-256 against metadata; retain transfer ID, document ID, checksum, source, and version for correlation.
6. A file-capable UiPath workflow or supported adapter must explicitly materialize/convert those bytes into the UiPath File representation required by the target IXP Extract node, then return that supported File output.
7. Only after that capability is verified in the actual UiPath tenant should the orchestrating Flow bind the returned File to extraction.

**A successful HTTP Request returning bytes does not establish that its output is a UiPath File variable.** The correct activity, runtime, output contract, temporary-file handling, and IXP binding must be discovered and verified during the later integration step. This document intentionally invents no UiPath activity signatures or provider endpoints.

## Security and trust

- Store the API key in managed credentials/connections; never put it in workflow source, query strings, logs, or public links.
- Protect local temporary files with runtime-appropriate permissions and retention. Use the platform's supported file lifecycle rather than an unrestricted download URL.
- Backend filenames are generated identifiers; original names are display metadata only. No server filesystem path is returned to UiPath.
- Declared document source and PDF text are evidence inputs, not instructions or authorization. Uploads do not change reference-data verification flags or financial state.
- Extraction outputs must eventually retain the exact source document ID/version/hash and provider run identity. This step returns no extraction values and implements no extraction-result endpoint.
- The current backend uses one service principal, not per-user/tenant authorization. Revisit identity, scopes, and reviewer controls before expanding beyond the fictional demo.

## Error handling for the later adapter

| Response | Planned handling |
|---|---|
| 401 / authentication configuration failure | Stop and repair credentials/configuration; do not fabricate a file |
| 404 | Report the unknown transfer/document or ownership mismatch |
| 409 document_not_ready | Inspect metadata; wait/retry only under a bounded policy for PENDING |
| 409 integrity/unavailable/FAILED | Escalate repository repair; do not extract changed or missing bytes |
| 503 transient storage/database error | Bounded retry; preserve document correlation |
| 200 binary PDF | Verify bytes, then perform the explicitly supported File conversion |

Reads can be repeated without creating new documents. Uploads create new IDs and are not idempotent; a future retrieval adapter should consume existing documents rather than upload duplicate copies after every retry.

## Later live verification gate

Verify tenant entitlement, the selected file-capable workflow/activity, authenticated binary retrieval, checksum preservation, actual File output type, and a real IXP extraction run with sanitized provider evidence. Test missing files, wrong ownership, corrupted bytes, timeout/retry, and low-confidence extraction. Use the separate evaluation variants under `mock_documents/generated/evaluation/` to measure layout robustness; no evaluation or extraction success is claimed yet.
