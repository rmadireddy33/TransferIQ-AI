from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.core.config import Settings
from backend.database.seed import seed_demo
from backend.database.seed_documents import seed_documents
from backend.main import create_app
from backend.models.documents import DocumentSource as S, DocumentType as T, TransferDocument
from backend.models.entities import AuditEvent
from backend.services import document_storage as storage
from backend.services.pdf_generation import document_data, render_pdf


@pytest.fixture
def doc_client(client, app):
    seed_demo(app.state.session_factory, include_scenarios=True)
    return client


@pytest.fixture
def pdf(doc_client, app):
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1002", T.ACCOUNT_STATEMENT)
    return render_pdf(data, T.ACCOUNT_STATEMENT)


def upload(client, auth, pdf, tid="TRF-1002", filename="fictional.pdf", kind="ACCOUNT_STATEMENT", source="DELIVERING_FIRM", mime="application/pdf"):
    return client.post(f"/api/transfers/{tid}/documents", headers=auth,
        data={"documentType": kind, "documentSource": source}, files={"file": (filename, pdf, mime)})


@pytest.mark.parametrize("kind,tid,action", [(T.TRANSFER_REQUEST, "TRF-1002", None),
    (T.ACCOUNT_STATEMENT, "TRF-1002", None), (T.CORPORATE_ACTION_NOTICE, "TRF-1002", "CA-2026-081"),
    (T.COST_BASIS_STATEMENT, "TRF-1004", None)])
def test_generation_is_valid_and_deterministic(doc_client, app, kind, tid, action):
    with app.state.session_factory() as session:
        data = document_data(session, tid, kind, action)
    first, second = render_pdf(data, kind), render_pdf(data, kind)
    assert first == second
    storage.validate_pdf(first, 10 * 1024 * 1024)
    reader = PdfReader(BytesIO(first), strict=True)
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "SAMPLE / FICTIONAL" in text
    assert tid in text


@pytest.mark.parametrize("layout", [1, 2, 3])
def test_statement_layouts_preserve_quantities(doc_client, app, layout):
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1002", T.ACCOUNT_STATEMENT)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(data, T.ACCOUNT_STATEMENT, layout))).pages)
    assert "40" in text[text.index("SEC-103"):text.index("SEC-104")]
    assert "120" in text[text.index("SEC-104"):text.index("SEC-105")]
    assert "2026-08-01" in text


@pytest.mark.parametrize("layout", [1, 2, 3])
def test_notice_matches_reference_record(doc_client, app, layout):
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1002", T.CORPORATE_ACTION_NOTICE, "CA-2026-081")
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(data, T.CORPORATE_ACTION_NOTICE, layout))).pages)
    for value in ("SEC-103", "STOCK_SPLIT", "2-for-1", "2026-08-10", "CA-2026-081", "reference-data repository"):
        assert value in text


def test_cost_basis_retains_multiple_stored_lots_and_missing_values(doc_client, app):
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1004", T.COST_BASIS_STATEMENT)
    assert len(data["lots"]) == 6
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(data, T.COST_BASIS_STATEMENT))).pages)
    assert all(lot["cost_basis_id"] in text for lot in data["lots"])
    assert "SEC-007" in text and "Unavailable" in text
    assert "No authoritative lot record" in text


def test_statement_multipage_repeats_headers_and_page_numbers(doc_client, app):
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1002", T.ACCOUNT_STATEMENT)
    # Layout stress fixture only; never persisted or added to the seeded documents.
    data = deepcopy(data)
    data["positions"] *= 15
    reader = PdfReader(BytesIO(render_pdf(data, T.ACCOUNT_STATEMENT)))
    assert len(reader.pages) >= 3
    for index, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        assert f"Page {index}" in text and "SAMPLE / FICTIONAL" in text
    assert "Quantity" in reader.pages[1].extract_text()


def test_upload_metadata_and_binary_download(doc_client, auth, pdf, app):
    response = upload(doc_client, auth, pdf)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["documentStatus"] == "READY" and body["fileSize"] == len(pdf)
    assert body["checksumSha256"] == storage.checksum(pdf)
    assert body["uploadedBy"] == "api-service" and not body["isSample"]
    assert "storagePath" not in body and "sampleKey" not in body
    assert doc_client.get(response.headers["Location"], headers=auth).json() == body
    listed = doc_client.get("/api/transfers/TRF-1002/documents?documentType=ACCOUNT_STATEMENT", headers=auth).json()
    assert listed["total"] == 1 and listed["items"][0] == body
    for path in [f"/api/documents/{body['documentId']}/download", f"/api/transfers/TRF-1002/documents/{body['documentId']}/download"]:
        result = doc_client.get(path, headers=auth)
        assert result.status_code == 200 and result.content == pdf
        assert result.headers["content-type"] == "application/pdf"
        assert result.headers["x-checksum-sha256"] == body["checksumSha256"]
        assert result.headers["content-disposition"].startswith("attachment;")
        assert result.headers["cache-control"] == "private, no-store"
        assert PdfReader(BytesIO(result.content)).pages[0].extract_text()
    with app.state.session_factory() as session:
        document = session.get(TransferDocument, body["documentId"])
        assert storage.document_path(app.state.settings, document).is_file()
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("DOCUMENT_READY:%"))) == 1


def test_upload_does_not_overwrite_existing_document(doc_client, auth, pdf):
    first = upload(doc_client, auth, pdf).json()
    second = upload(doc_client, auth, pdf).json()
    assert first["documentId"] != second["documentId"]
    assert first["fileName"] != second["fileName"]


def test_all_document_routes_require_auth(doc_client, auth, pdf):
    doc = upload(doc_client, auth, pdf).json()
    assert upload(doc_client, {}, pdf).status_code == 401
    for route in ["/api/transfers/TRF-1002/documents", f"/api/documents/{doc['documentId']}",
                  f"/api/documents/{doc['documentId']}/download", f"/api/transfers/TRF-1002/documents/{doc['documentId']}/download"]:
        assert doc_client.get(route).status_code == 401
        assert doc_client.get(route, headers={"X-API-Key": "wrong"}).status_code == 401


@pytest.mark.parametrize("kind,source", [("INVALID", "CLIENT_UPLOAD"), ("ACCOUNT_STATEMENT", "INVALID")])
def test_invalid_enums(doc_client, auth, pdf, kind, source):
    assert upload(doc_client, auth, pdf, kind=kind, source=source).status_code == 422


@pytest.mark.parametrize("data,filename,mime,expected", [(b"plain text", "file.pdf", "application/pdf", 422),
    (b"%PDF-1.7\ncorrupted\n%%EOF", "file.pdf", "application/pdf", 422),
    (b"plain text", "file.txt", "text/plain", 415), (b"%PDF-1.7", "file.pdf", "application/pdf", 422)])
def test_invalid_files(doc_client, auth, data, filename, mime, expected):
    assert upload(doc_client, auth, data, filename=filename, mime=mime).status_code == expected


def test_pdf_disguised_as_other_type_rejected(doc_client, auth, pdf):
    assert upload(doc_client, auth, pdf, filename="file.txt").status_code == 415
    assert upload(doc_client, auth, pdf, mime="image/png").status_code == 415


@pytest.mark.parametrize("filename", ["../private.pdf", "/tmp/private.pdf"])
def test_filename_paths_are_rejected(doc_client, auth, pdf, filename):
    assert upload(doc_client, auth, pdf, filename=filename).status_code == 400


def test_windows_filename_normalization_still_uses_internal_storage(doc_client, auth, pdf, app):
    # python-multipart strips legacy browser Windows paths before handing us the name.
    response = upload(doc_client, auth, pdf, filename="C:\\private.pdf")
    assert response.status_code == 201
    assert response.json()["originalFileName"] == "private.pdf"
    with app.state.session_factory() as session:
        row = session.get(TransferDocument, response.json()["documentId"])
        path = storage.document_path(app.state.settings, row)
        assert path.is_relative_to(app.state.settings.data_dir)
        assert path.name == row.document_id + ".pdf"


def test_encrypted_pdf_rejected(doc_client, auth):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("test-only-password")
    stream = BytesIO()
    writer.write(stream)
    assert upload(doc_client, auth, stream.getvalue()).status_code == 422


def test_file_size_limits_and_chunked_body(doc_client, auth, pdf, app):
    app.state.settings = app.state.settings.model_copy(update={"max_document_bytes": 1024})
    assert upload(doc_client, auth, pdf).status_code == 413
    assert doc_client.post("/api/transfers/TRF-1002/documents", headers={**auth, "Content-Length": "999999"}, content=b"x").status_code == 413
    headers = {**auth, "Content-Type": "multipart/form-data; boundary=test-boundary"}
    chunks = iter([b'--test-boundary\r\nContent-Disposition: form-data; name="file"; filename="test.pdf"\r\nContent-Type: application/pdf\r\n\r\n', b'x' * 300000, b'\r\n--test-boundary--\r\n'])
    assert doc_client.post("/api/transfers/TRF-1002/documents", headers=headers, content=chunks).status_code == 413
    assert doc_client.get("/api/transfers/TRF-1002/documents", headers=auth).json()["total"] == 0


def test_unknown_transfer_document_and_wrong_owner(doc_client, auth, pdf):
    assert upload(doc_client, auth, pdf, tid="absent").status_code == 404
    assert doc_client.get("/api/transfers/absent/documents", headers=auth).status_code == 404
    assert doc_client.get("/api/documents/absent/download", headers=auth).status_code == 404
    document = upload(doc_client, auth, pdf).json()
    assert doc_client.get(f"/api/transfers/TRF-1001/documents/{document['documentId']}/download", headers=auth).status_code == 404


def test_checksum_tampering_blocks_download(doc_client, auth, pdf, app):
    document = upload(doc_client, auth, pdf).json()
    with app.state.session_factory() as session:
        row = session.get(TransferDocument, document["documentId"])
        storage.document_path(app.state.settings, row).write_bytes(b"changed")
    response = doc_client.get(f"/api/documents/{document['documentId']}/download", headers=auth)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_integrity_failure"


def test_tampered_storage_reference_cannot_read_arbitrary_file(doc_client, auth, pdf, app):
    document = upload(doc_client, auth, pdf).json()
    with app.state.session_factory.begin() as session:
        session.get(TransferDocument, document["documentId"]).storage_path = "../../.env"
    assert doc_client.get(f"/api/documents/{document['documentId']}/download", headers=auth).status_code == 409


def test_missing_file_returns_safe_error(doc_client, auth, pdf, app):
    document = upload(doc_client, auth, pdf).json()
    with app.state.session_factory() as session:
        path = storage.document_path(app.state.settings, session.get(TransferDocument, document["documentId"]))
    path.unlink()
    result = doc_client.get(f"/api/documents/{document['documentId']}/download", headers=auth)
    assert result.status_code == 409 and str(path) not in result.text


def test_document_seed_is_idempotent_and_preserves_uploads(doc_client, auth, pdf, app, tmp_path):
    uploaded = upload(doc_client, auth, pdf).json()
    count, manifest = seed_documents(app.state.session_factory, app.state.settings, tmp_path / "samples")
    assert count == 16 and len(manifest) == 16
    assert seed_documents(app.state.session_factory, app.state.settings, tmp_path / "samples")[0] == 0
    assert doc_client.get(f"/api/documents/{uploaded['documentId']}/download", headers=auth).content == pdf
    primary = doc_client.get("/api/transfers/TRF-1002/documents", headers=auth).json()
    all_docs = doc_client.get("/api/transfers/TRF-1002/documents?includeEvaluation=true", headers=auth).json()
    assert primary["total"] == 4  # 3 seeded primary documents plus one upload.
    assert all_docs["total"] == 8
    for item in manifest:
        assert storage.checksum(Path(item["samplePath"]).read_bytes()) == item["checksumSha256"]


def test_document_persistence_after_restart(doc_client, auth, pdf, app, settings):
    document = upload(doc_client, auth, pdf).json()
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/documents/{document['documentId']}", headers=auth).json() == document
        assert restarted.get(f"/api/documents/{document['documentId']}/download", headers=auth).content == pdf


def test_pending_file_recovered_after_restart(doc_client, auth, pdf, app, settings, monkeypatch):
    def interrupted(*args):
        raise OSError("injected storage interruption")
    with monkeypatch.context() as patch:
        patch.setattr(storage, "_publish", interrupted)
        assert upload(doc_client, auth, pdf).status_code == 503
    with app.state.session_factory() as session:
        pending = session.scalar(select(TransferDocument))
        assert pending.document_status == "PENDING"
        identifier = pending.document_id
    assert doc_client.get(f"/api/documents/{identifier}/download", headers=auth).status_code == 409
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/documents/{identifier}/download", headers=auth).content == pdf


def test_database_failure_removes_unregistered_staging_file(doc_client, auth, pdf, app):
    with app.state.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TRIGGER test_document_failure BEFORE INSERT ON transfer_documents BEGIN SELECT RAISE(ABORT, 'injected'); END")
    assert upload(doc_client, auth, pdf).status_code == 409
    assert list((app.state.settings.data_dir / "staging").glob("*.part")) == []


def test_published_file_recovers_after_final_metadata_failure(doc_client, auth, pdf, app, settings):
    with app.state.engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER test_ready_failure BEFORE UPDATE OF document_status ON transfer_documents
            WHEN NEW.document_status='READY' BEGIN SELECT RAISE(ABORT, 'injected finalization failure'); END""")
    assert upload(doc_client, auth, pdf).status_code == 409
    with app.state.session_factory() as session:
        row = session.scalar(select(TransferDocument))
        assert row.document_status == "PENDING"
        assert storage.document_path(settings, row).is_file()
        identifier = row.document_id
    with app.state.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER test_ready_failure")
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/documents/{identifier}/download", headers=auth).content == pdf


def test_new_generated_content_creates_version_without_overwrite(doc_client, app, pdf):
    first, _ = storage.save_document(app.state.session_factory, app.state.settings, "TRF-1002", pdf,
                                    "sample.pdf", T.ACCOUNT_STATEMENT, S.DELIVERING_FIRM, sample_key="test-layout")
    with app.state.session_factory() as session:
        data = document_data(session, "TRF-1002", T.ACCOUNT_STATEMENT)
    changed = render_pdf(data, T.ACCOUNT_STATEMENT, layout=2)
    second, created = storage.save_document(app.state.session_factory, app.state.settings, "TRF-1002", changed,
                                    "sample.pdf", T.ACCOUNT_STATEMENT, S.DELIVERING_FIRM, sample_key="test-layout")
    assert created and second.version == 2 and first.document_id != second.document_id
    assert storage.read_document(app.state.settings, first) == pdf
    assert storage.read_document(app.state.settings, second) == changed


def test_document_openapi_is_binary_and_multipart(doc_client):
    spec = doc_client.get("/openapi.json").json()
    assert "multipart/form-data" in spec["paths"]["/api/transfers/{transferId}/documents"]["post"]["requestBody"]["content"]
    assert "application/pdf" in spec["paths"]["/api/documents/{documentId}/download"]["get"]["responses"]["200"]["content"]
