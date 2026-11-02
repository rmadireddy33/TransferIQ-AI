# Step 4 executed verification

Completed on 2026-11-01 (America/New_York) in the existing project virtual environment. No frontend, live UiPath integration, cloud deployment, or financial correction was implemented.

## Dependencies and tests

Executed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r scripts/requirements-pdf-qa.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Installed ReportLab 4.5.1, pypdf 6.21.4, and python-multipart 0.0.33 for the backend. PDFium 5.14.0 is an optional development-only renderer; Poppler was unavailable in this Windows environment. Pillow and charset-normalizer were installed as dependencies.

All 120 existing tests passed after the additive schema/routing changes. The first expanded run reported **155 passed, 1 failed**: a test expected a legacy Windows filename path to reach the handler unchanged. Inspection confirmed python-multipart intentionally reduces that form to its basename. The test now verifies the accepted basename is stored under a generated internal path; other retained traversal paths remain rejected.

The final complete run, including added restart-recovery and migration checks, reported:

```text
159 passed, 1 warning in 24.05s
```

The warning is the previously observed upstream Starlette/httpx TestClient deprecation. No warning was suppressed. `pip check` reported `No broken requirements found.` Tests use isolated temporary databases/document directories and preserve Steps 2/3 coverage.

Document checks include deterministic generation, all three statement/notice layouts, parseability, source quantities, reference evidence, missing basis, multipage tables, upload/metadata/download contracts, authentication, invalid type/source/MIME/extension, corrupt/encrypted PDFs, file and chunked-body limits, unknown IDs, wrong transfer ownership, path traversal, checksum tampering, missing files, idempotent seeds, version preservation, database failures, recovery before/after file publication, and restart persistence. Migration tests cover existing v1/v2 data and transaction rollback.

## Migration and generation

Stopped the old backend and created a SQLite-consistent backup:

```text
data/backups/pre-step4-20261101T041829351758Z.db
```

The backup filename uses UTC. Applied schema v2 -> v3, generated 16 PDFs, and registered 16 document rows. A second generation/seed inserted 0 documents. Every pre-existing financial, reconciliation, and audit row was compared with its original values and preserved; the foreign-key check was clean.

Both documented CLIs were also executed afterward:

```powershell
.\.venv\Scripts\python.exe -m backend.database.seed_documents
.\.venv\Scripts\python.exe -m backend.database.seed
```

The PDF-only CLI reported `Fictional PDFs ready: 16; new document records: 0`. The full seeder reported 0 financial rows and 0 document records inserted. It did not overwrite user uploads or original custody positions.

## Visual and binary verification

Executed `python -m scripts.render_pdf_qa`. Rendered all 16 generated PDFs plus a five-page layout-only stress PDF: **17 PDFs / 21 pages**. Inspected both complete contact sheets and full-size source-statement/cost-basis pages. Headers, tables, page breaks, missing-value text, and footers were readable without clipping or overlap. The stress fixture is not registered as transfer evidence.

Started Uvicorn with `scripts/start-backend.ps1 -NoReload` on port 8000. Ran `scripts/verify-documents.ps1` using the existing local key without printing it, followed by the existing `verify-backend.ps1`:

- Primary document counts were 2, 3, 2, 3, and 2 for TRF-1001 through TRF-1005.
- Filtered listing, metadata lookup, and authenticated scoped binary download succeeded.
- The downloaded TRF-1002 statement parsed with selectable text and contained the expected source securities.
- Its length and SHA-256 matched metadata **and the generated original**.
- All 14 existing GET checks, including Swagger/OpenAPI, returned HTTP 200.

Downloaded file:

```text
data/verification/DOC-6f50bb82-689a-4303-a199-17d533b7ccdd.pdf
SHA-256: 173f27a02f948e5c96afd5acd90a67425275457896e956f292ec2f755f30f47d
```

The actual downloaded file was then opened/rendered with PDFium and visually inspected. It matches the original statement: SEC-103 has 40 shares, and SEC-104 has 120 shares. This was an actual HTTP download, not a direct-file substitute.

Captured all 16 metadata records, stopped Uvicorn, restarted it, then fetched all 16 records and downloaded all 16 PDFs again. Metadata matched exactly and every checksum remained valid. `/docs` returned HTTP 200. The restarted server remains running at **http://127.0.0.1:8000/docs**.

HTTP upload/authentication/failure cases were tested with FastAPI TestClient and isolated storage; live development checks were read-only downloads/listings. No new upload was added to the development repository merely for verification.

## Source files

Added:

```text
backend/api/documents.py
backend/api/upload_limit.py
backend/database/seed_documents.py
backend/models/documents.py
backend/schemas/documents.py
backend/services/document_storage.py
backend/services/pdf_generation.py
tests/test_documents.py
scripts/verify-documents.ps1
scripts/render_pdf_qa.py
scripts/requirements-pdf-qa.txt
docs/DOCUMENT_API.md
docs/IXP_INTEGRATION_PLAN.md
docs/STEP4_VERIFICATION.md
```

Updated: backend configuration, dependencies, application lifespan/routers, ordered migrations, the seed CLI, migration tests, `.env.example`, `.gitignore`, `README.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md`, and `AGENTS.md`. Runtime PDFs, generated samples, previews, downloads, and backups are ignored. No credentials were printed or embedded in source; the existing local API key was preserved.

## Generated paths

All paths below are relative to `C:\Projects\TransferIQ-AI`. `mock_documents/generated/manifest.json` also records absolute sample/runtime paths, document IDs, checksums, input fingerprints, layout number, and evaluation flag. Runtime copies use the hashed transfer bucket and generated document filename; they are independent of the reproducible sample folder.

| Transfer / type / layout | Reproducible sample path | Runtime storage path |
|---|---|---|
| TRF-1001 / TRANSFER_REQUEST / 1 | mock_documents/generated/primary/TRF-1001/transfer_request-layout1-6a32f689594c.pdf | data/documents/3b4bd3b730368bebdd46abbef5cd7531/DOC-74280d28-fbe1-4c7c-9047-6f21ab9cb343.pdf |
| TRF-1001 / ACCOUNT_STATEMENT / 1 | mock_documents/generated/primary/TRF-1001/account_statement-layout1-3b501067d32d.pdf | data/documents/3b4bd3b730368bebdd46abbef5cd7531/DOC-bb4819a5-95a1-459a-b6b7-36fbd0e7dacc.pdf |
| TRF-1002 / TRANSFER_REQUEST / 1 | mock_documents/generated/primary/TRF-1002/transfer_request-layout1-bcff313c902c.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-e10a8702-ee68-4bad-bfbe-7457a4029ff3.pdf |
| TRF-1002 / ACCOUNT_STATEMENT / 1 | mock_documents/generated/primary/TRF-1002/account_statement-layout1-173f27a02f94.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-6f50bb82-689a-4303-a199-17d533b7ccdd.pdf |
| TRF-1003 / TRANSFER_REQUEST / 1 | mock_documents/generated/primary/TRF-1003/transfer_request-layout1-69f4b871677a.pdf | data/documents/bb574489fc6b58fe3a85ddaa21fc1005/DOC-5ca673aa-f352-40da-b369-e9d88a7810d6.pdf |
| TRF-1003 / ACCOUNT_STATEMENT / 1 | mock_documents/generated/primary/TRF-1003/account_statement-layout1-91d14b958603.pdf | data/documents/bb574489fc6b58fe3a85ddaa21fc1005/DOC-8f40e65b-b11b-43b5-b70a-f9e02fcac2c2.pdf |
| TRF-1004 / TRANSFER_REQUEST / 1 | mock_documents/generated/primary/TRF-1004/transfer_request-layout1-e76cd08cabc7.pdf | data/documents/09f1f6b3d6cda48595a85befa92e8a53/DOC-1b854f44-4cf2-4e5d-93e9-beefc1f8823d.pdf |
| TRF-1004 / ACCOUNT_STATEMENT / 1 | mock_documents/generated/primary/TRF-1004/account_statement-layout1-8b46d48f032d.pdf | data/documents/09f1f6b3d6cda48595a85befa92e8a53/DOC-387a1841-5da8-4cea-a9ce-23c195a567cf.pdf |
| TRF-1005 / TRANSFER_REQUEST / 1 | mock_documents/generated/primary/TRF-1005/transfer_request-layout1-b0edd25019b3.pdf | data/documents/71814434653fb4da096ea38d9be66933/DOC-66a6f169-2ca1-4519-bc47-61dc81bfd873.pdf |
| TRF-1005 / ACCOUNT_STATEMENT / 1 | mock_documents/generated/primary/TRF-1005/account_statement-layout1-c1dfb91123ba.pdf | data/documents/71814434653fb4da096ea38d9be66933/DOC-e7899abf-3cce-42a9-b9e6-fbfbe6d8ce4a.pdf |
| TRF-1002 / CORPORATE_ACTION_NOTICE / 1 | mock_documents/generated/primary/TRF-1002/corporate_action_notice-layout1-a4ea1506d5a3.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-00b5147b-c961-47b9-a778-7c3a5b4bdef2.pdf |
| TRF-1004 / COST_BASIS_STATEMENT / 1 | mock_documents/generated/primary/TRF-1004/cost_basis_statement-layout1-1f3f716a82da.pdf | data/documents/09f1f6b3d6cda48595a85befa92e8a53/DOC-150c67b7-2622-4cb3-b6ca-541027d93f7a.pdf |
| TRF-1002 / ACCOUNT_STATEMENT / 2 | mock_documents/generated/evaluation/TRF-1002/account_statement-layout2-b67267d13572.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-653c5c96-e4fe-4834-b238-86795bf52f89.pdf |
| TRF-1002 / CORPORATE_ACTION_NOTICE / 2 | mock_documents/generated/evaluation/TRF-1002/corporate_action_notice-layout2-687a6c4594b8.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-ffa0eaea-59cc-4ce9-9eb6-2e2513396b9e.pdf |
| TRF-1002 / ACCOUNT_STATEMENT / 3 | mock_documents/generated/evaluation/TRF-1002/account_statement-layout3-b4657ecbae8c.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-883fa56f-d5f1-42e0-8fcc-608812630002.pdf |
| TRF-1002 / CORPORATE_ACTION_NOTICE / 3 | mock_documents/generated/evaluation/TRF-1002/corporate_action_notice-layout3-b0509128e1b2.pdf | data/documents/bd6a6f09a89348f2fbfce7c048c648e2/DOC-0303e6ed-f91b-44d2-83f1-897111c73bec.pdf |
