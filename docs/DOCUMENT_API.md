# PDF document repository

Step 4 implements private PDF uploads, metadata, binary downloads, deterministic fictional document generation, and SQLite metadata persistence. No financial positions, reference evidence, basis records, or reconciliation results are modified by document generation or upload.

## Types, sources, and ownership

Supported `documentType` values:

| Type | Generated content |
|---|---|
| `TRANSFER_REQUEST` | Transfer/client/firm/account details and a clearly fictional authorization placeholder |
| `ACCOUNT_STATEMENT` | Original delivering snapshot holdings; identifier-mapping appendix when reference records exist |
| `CORPORATE_ACTION_NOTICE` | Independent reference-data notice linked to a relevant transfer; ratios, dates, verification flag, and evidence reference from CorporateAction |
| `COST_BASIS_STATEMENT` | Stored tax lots, quantities, acquisition dates, amounts, and lot references; absent values explicitly unavailable |

Supported `documentSource` values: `CLIENT_UPLOAD`, `TRANSFER_OPERATIONS`, `DELIVERING_FIRM`, and `REFERENCE_DATA`. Source identifies declared provenance, not proof of authenticity. Uploading a notice never marks a corporate action verified and never makes its contents authoritative.

Each `documentId` is a server-generated `DOC-<UUID>` and belongs to exactly one existing `transferId`, enforced by a foreign key. All upload, metadata, and download routes require `X-API-Key`. The existing single service principal has access to all fictional transfers; this step does not implement individual user roles or tenant isolation. The transfer-scoped download verifies document ownership and returns 404 on mismatch. No anonymous download links or static document mounts exist.

## Endpoints

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/transfers/{transferId}/documents` | Multipart `file`, `documentType`, `documentSource`; 201 metadata and Location |
| GET | `/api/transfers/{transferId}/documents` | Paginated metadata; optional `documentType` filter |
| GET | `/api/documents/{documentId}` | One metadata record |
| GET | `/api/documents/{documentId}/download` | Actual PDF bytes |
| GET | `/api/transfers/{transferId}/documents/{documentId}/download` | Same binary response with transfer ownership check |

Lists use `items`, `total`, `limit`, and `offset` (default 50, maximum 100). Evaluation variants are excluded by default; use `includeEvaluation=true` to include them. Metadata can include PENDING/FAILED records; select `documentStatus=READY` before attempting retrieval. If several versions exist, inspect their version/creation time and select the intended evidence rather than blindly using the first row.

Metadata includes `documentId`, `transferId`, type/source, safe internal `fileName`, display-only `originalFileName`, MIME type, size, SHA-256, server-assigned uploader, UTC times, status, version, `isSample`, and `evaluationOnly`. Absolute paths, storage keys, and sample-deduplication keys are not exposed.

Downloads use `Content-Type: application/pdf`, attachment `Content-Disposition` with the generated filename, `X-Checksum-SHA256`, `X-Content-Type-Options: nosniff`, and `Cache-Control: private, no-store`. Size and checksum are checked before returning the bytes. The response is binary, not JSON, base64, a public URL, or a UiPath File object.

### Validation and error contract

Uploads require `.pdf` extension, `application/pdf` MIME type, a PDF header/end marker, and strict [pypdf parsing](https://pypdf.readthedocs.io/en/3.15.3/modules/PdfReader.html). Encrypted, empty, corrupt, invalid-page, or over-limit files are rejected. Content streams are parsed; supported PDFs have 1-200 pages, with a 64 MiB decompressed per-page validation budget. This checks file integrity, not signatures, provenance, or malware safety. Uploaded document text remains untrusted evidence.

`MAX_DOCUMENT_BYTES` defaults to `10485760` bytes (10 MiB). It is configurable from 1 KiB to 100 MiB. A transport guard limits total multipart input to this value plus 256 KiB of form overhead, including chunked requests; the file itself still must fit the configured limit. Multipart handling uses FastAPI's [File/UploadFile contract](https://fastapi.tiangolo.com/tutorial/request-files/).

| Status | Meaning |
|---|---|
| 400 | Unsafe display filename retained by the parser |
| 401 | Missing/incorrect service API key |
| 404 | Unknown transfer/document or transfer/document ownership mismatch |
| 409 | Document not ready, unavailable, checksum mismatch, invalid internal reference, or database conflict |
| 413 | File or multipart request exceeds its limit |
| 415 | Unsupported extension or MIME type |
| 422 | Invalid type/source form values or invalid/unsupported PDF |
| 503 | Authentication configuration or persistent storage unavailable |

Parser normalization can strip a legacy Windows filename path before validation. Remaining path separators/control characters are rejected. The original filename is never used as a storage path. Errors do not expose file contents or server paths.

## Storage, consistency, and versions

The `transfer_documents` table is added by transactional schema migration v2 -> v3. v1 -> v2 -> v3 upgrades remain supported. Existing financial and reconciliation tables are preserved. PDF bytes are not stored in SQLite.

```text
DATA_DIR/                        # ./data locally; /data on Railway
  transferiq.db
  documents/
    <hash-of-transferId>/
      DOC-<UUID>.pdf
  staging/
    DOC-<UUID>.pdf.part
```

Hashed transfer buckets avoid putting even a database-supplied transfer string into a filesystem path. The metadata foreign key retains the human-readable transfer relationship. Every path must remain under resolved DATA_DIR; symlinks/junctions and invalid stored references are rejected. A different transfer's document is never overwritten.

Storage follows a recoverable sequence:

1. Validate and checksum the bytes, then write and flush an exclusive temporary file in DATA_DIR/staging.
2. Commit PENDING metadata containing the expected size/hash and generated storage reference.
3. Publish complete bytes with a same-volume, no-overwrite hard link, then remove the staging link. This requires a filesystem supporting hard links; failure returns a storage error and never falls back to an unsafe overwrite.
4. Verify the final bytes, then commit READY status and its audit event together.

Startup recovery resumes PENDING entries from valid staged or published files. Missing/corrupt pending bytes lead to FAILED status and are not served. Orphan staging files created before metadata commit remain private for operator inspection; there is no automatic deletion/reset of unknown files. Registered files that later disappear or change are blocked on download. Database and filesystem changes cannot share one transaction, so this explicit recovery sequence handles their boundary.

Generated sample identities combine a logical recipe and PDF content checksum. Identical generation reuses the same document; changed generated content creates a new document/version and preserves earlier bytes. A sample version counter is scoped to the logical recipe. Ordinary uploads always create separate document IDs with version 1; this API has no replacement/deletion endpoint. Upload retries are not deduplicated automatically. Operators should check returned metadata before repeating an upload after an uncertain response.

For backups, coordinate a SQLite-consistent database backup with immutable document files and a checksum manifest. A database-only backup taken after documents exist cannot restore document bytes. Runtime data remains outside source folders. The future Railway deployment must mount one persistent volume at `/data` and set DATA_DIR accordingly; no deployment was performed in this step.

## Reproducible samples and evaluation variants

```text
DATA_DIR/sample_exports/
  primary/TRF-1001/...pdf
  primary/TRF-1002/...pdf
  primary/TRF-1003/...pdf
  primary/TRF-1004/...pdf
  primary/TRF-1005/...pdf
  evaluation/TRF-1002/...pdf
  manifest.json
```

This folder holds explicit CLI generation outputs, not live uploads. It defaults to `./data/sample_exports` locally and is excluded from Git with the data directory. The private repository stores independent copies under DATA_DIR/documents. `manifest.json` maps all 16 sample paths to document IDs, runtime paths, layout numbers, input fingerprints, and checksums. [STEP4_VERIFICATION.md](STEP4_VERIFICATION.md) retains historical paths from that earlier verification; new exports use DATA_DIR.

There are 12 primary samples: requests and statements for all five transfers, one TRF-1002 action notice, and one TRF-1004 basis statement. Four separate evaluation samples provide account statement layouts 2/3 and action-notice layouts 2/3. Layouts use gridded navy, banded teal, and ruled monochrome treatments with consistent content fields, standard fonts, selectable text, SAMPLE / FICTIONAL markings, and page numbers. Tables repeat headers on subsequent pages.

TRF-1002's original statement shows SEC-103 at 40 and SEC-104 at 120; the separate reference notice displays STOCK_SPLIT (stored reference code SPLIT), 2-for-1, and the stored effective date 2026-08-10. TRF-1003's statement carries the stored identifier-mapping appendix. TRF-1004 lists its six authoritative lots and marks SEC-007 as unavailable. No artificial lots were invented or split; no currency is asserted because the current basis model has no currency field.

Reproduce with the project virtual environment:

```powershell
cd C:\Projects\TransferIQ-AI
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.database.init_db
.\.venv\Scripts\python.exe -m backend.database.seed
# Regenerate/register PDFs only, using already seeded financial records:
.\.venv\Scripts\python.exe -m backend.database.seed_documents
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\start-backend.ps1
```

Stop an existing server before starting another on the same port. The full seed CLI includes document generation and the export manifest, while the fixture functions used by earlier tests keep their original scope. Startup seeding is disabled by default. With `SEED_DEMO_DATA=1`, startup adds missing fictional records and sample recipes directly to the private repository, without creating export copies/manifest or re-rendering registered samples. It preserves existing document references and fails on missing/corrupt registered bytes. See [Railway initialization](RAILWAY_DEPLOYMENT.md).

Optional visual QA (PDFium is a development-only fallback because Poppler was unavailable in this Windows environment):

```powershell
.\.venv\Scripts\python.exe -m pip install -r scripts/requirements-pdf-qa.txt
.\.venv\Scripts\python.exe -m scripts.render_pdf_qa
```

Renders go to `DATA_DIR/verification/pdf-qa/`. The long statement generated there is a layout stress fixture only and is never registered as financial evidence. Run the explicit seed CLI first to create `DATA_DIR/sample_exports/manifest.json`; this is also required by `verify-documents.ps1`.

## PowerShell upload/download verification

In a second terminal, load the same configured key without printing it:

```powershell
cd C:\Projects\TransferIQ-AI
$env:API_KEY = & .\.venv\Scripts\python.exe -c "from backend.core.config import Settings; print(Settings.from_environment().api_key.get_secret_value())"
$headers = @{ 'X-API-Key' = $env:API_KEY }
.\scripts\verify-documents.ps1
$list = Invoke-RestMethod 'http://127.0.0.1:8000/api/transfers/TRF-1002/documents?documentType=ACCOUNT_STATEMENT' -Headers $headers
$document = $list.items[0]
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/documents/$($document.documentId)/download" `
    -Headers $headers -OutFile .\data\verification\statement.pdf
Get-FileHash .\data\verification\statement.pdf -Algorithm SHA256
```

The variable assignment captures the key; do not run the embedded print command on its own or share its output. If the server key exists only in another terminal's process environment, supply that same value securely instead.

Multipart upload from Windows PowerShell 5.1 or newer using `curl.exe` (each execution creates a new document):

```powershell
$dataDir = & .\.venv\Scripts\python.exe -c "from backend.core.config import Settings; print(Settings.from_environment().data_dir)"
$manifest = Get-Content -Raw (Join-Path $dataDir 'sample_exports/manifest.json') | ConvertFrom-Json
$samplePath = ($manifest | Where-Object { $_.transferId -eq 'TRF-1002' -and $_.documentType -eq 'ACCOUNT_STATEMENT' -and -not $_.evaluationOnly } | Select-Object -First 1).samplePath
# Send the secret header through stdin, keeping it out of curl's command-line arguments.
"X-API-Key: $env:API_KEY" | curl.exe --fail-with-body -H '@-' `
    -F "file=@$samplePath;type=application/pdf" `
    -F 'documentType=ACCOUNT_STATEMENT' -F 'documentSource=DELIVERING_FIRM' `
    http://127.0.0.1:8000/api/transfers/TRF-1002/documents
```

Swagger is at <http://127.0.0.1:8000/docs>. Authorize with the local key, expand **Documents**, select the type/source fields, and choose a PDF. The download route returns a file. Future UiPath file binding is described separately in [IXP_INTEGRATION_PLAN.md](IXP_INTEGRATION_PLAN.md).
