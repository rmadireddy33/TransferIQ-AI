"""Private PDF storage with durable pending metadata and no-clobber publication."""
import hashlib
import os
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import func, select, update

from backend.api.dependencies import fail
from backend.models.documents import TransferDocument
from backend.models.entities import AuditEvent, Transfer
from backend.models.types import utcnow
from backend.services.transfers import require_record


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_pdf(data: bytes, limit: int):
    if len(data) > limit:
        fail(413, "document_too_large", f"PDF exceeds the {limit}-byte limit")
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        fail(422, "invalid_pdf", "PDF header or end marker is missing")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted documents are unsupported")
        if not 1 <= len(reader.pages) <= 200:
            raise ValueError("PDF must contain between 1 and 200 pages")
        for page in reader.pages:
            if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
                raise ValueError("Invalid page dimensions")
            content = page.get_contents()
            if content is not None:
                if len(content.get_data()) > 64 * 1024 * 1024:
                    raise ValueError("Page content exceeds validation budget")
                _ = content.operations
    except Exception:
        # Never expose parser exceptions or document text to callers/logs.
        fail(422, "invalid_pdf", "PDF is corrupt, encrypted, empty, or exceeds supported parsing limits")


def display_filename(name: str | None):
    if (not name or len(name) > 200 or any(ord(char) < 32 for char in name)
            or any(char in name for char in '/\\:') or name in {".", ".."}):
        fail(400, "invalid_filename", "Use a plain PDF filename without paths or control characters")
    if not name.lower().endswith(".pdf"):
        fail(415, "unsupported_file", "Only .pdf documents are accepted")
    return name


def storage_key(transfer_id, document_id):
    if not re.fullmatch(r"DOC-[0-9a-f-]{36}", document_id):
        fail(409, "invalid_storage_reference", "Document storage reference is invalid")
    bucket = hashlib.sha256(transfer_id.encode()).hexdigest()[:32]
    return f"documents/{bucket}/{document_id}.pdf"


def private_path(settings, relative):
    root = settings.data_dir.resolve()
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        fail(409, "invalid_storage_reference", "Document storage reference is invalid")
    # Reject symlinks/junctions even if they lead to another transfer in DATA_DIR.
    cursor = candidate
    while cursor != root:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            fail(409, "invalid_storage_reference", "Linked document storage paths are not supported")
        cursor = cursor.parent
    return candidate


def document_path(settings, document):
    expected = storage_key(document.transfer_id, document.document_id)
    if document.storage_path != expected or document.file_name != f"{document.document_id}.pdf":
        fail(409, "invalid_storage_reference", "Document storage reference is invalid")
    return private_path(settings, expected)


def stage_path(settings, document_id):
    storage_key("validation", document_id)
    return private_path(settings, f"staging/{document_id}.pdf.part")


def _bytes_match(path, document):
    try:
        with path.open("rb") as handle:
            data = handle.read(document.file_size + 1)
        return len(data) == document.file_size and checksum(data) == document.checksum_sha256
    except FileNotFoundError:
        return False


def _publish(staged, final):
    final.parent.mkdir(parents=True, exist_ok=True)
    # A hard link atomically makes the complete bytes visible and never replaces
    # an existing file. Staging and documents must reside on the same volume.
    os.link(staged, final)
    staged.unlink()
    if hasattr(os, "O_DIRECTORY"):
        descriptor = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def finalize_document(factory, settings, document_id):
    with factory() as session:
        document = require_record(session, TransferDocument, document_id)
        if document.document_status != "PENDING":
            return document
    final, staged = document_path(settings, document), stage_path(settings, document_id)
    if not final.exists() and _bytes_match(staged, document):
        try:
            _publish(staged, final)
        except FileExistsError:
            pass  # Concurrent recovery: verify the published bytes below.
    ready = _bytes_match(final, document)
    if ready and _bytes_match(staged, document):
        staged.unlink(missing_ok=True)
    with factory.begin() as session:
        changed = session.execute(update(TransferDocument).where(
            TransferDocument.document_id == document_id, TransferDocument.document_status == "PENDING").values(
            document_status="READY" if ready else "FAILED", updated_at=utcnow())).rowcount
        if changed:
            transfer = require_record(session, Transfer, document.transfer_id)
            session.add(AuditEvent(event_id=str(uuid4()), transfer_id=document.transfer_id, actor=document.uploaded_by,
                action=f"DOCUMENT_{'READY' if ready else 'FAILED'}:{document_id}",
                previous_status=transfer.status.value, new_status=transfer.status.value))
    with factory() as session:
        return require_record(session, TransferDocument, document_id)


def recover_pending_documents(factory, settings):
    with factory() as session:
        ids = session.scalars(select(TransferDocument.document_id).where(TransferDocument.document_status == "PENDING")).all()
    for identifier in ids:
        finalize_document(factory, settings, identifier)


def read_document(settings, document):
    if document.document_status != "READY":
        fail(409, "document_not_ready", "Document is not available for download")
    path = document_path(settings, document)
    try:
        with path.open("rb") as handle:
            data = handle.read(document.file_size + 1)
    except FileNotFoundError:
        fail(409, "document_unavailable", "Stored PDF is unavailable; repository repair is required")
    if len(data) != document.file_size or checksum(data) != document.checksum_sha256:
        fail(409, "document_integrity_failure", "Stored PDF failed its size/checksum verification")
    return data


def save_document(factory, settings, transfer_id, data, filename, document_type, document_source,
                  *, sample_key=None, evaluation_only=False):
    filename = display_filename(filename)
    validate_pdf(data, settings.max_document_bytes)
    digest = checksum(data)
    seed_key = checksum(f"{sample_key}:{digest}".encode()) if sample_key else None
    with factory() as session:
        require_record(session, Transfer, transfer_id)
        existing = session.scalar(select(TransferDocument).where(TransferDocument.seed_key == seed_key)) if seed_key else None
        version = (session.scalar(select(func.max(TransferDocument.version)).where(
            TransferDocument.sample_key == sample_key)) or 0) + 1 if sample_key else 1
    if existing:
        if existing.document_status == "PENDING":
            existing = finalize_document(factory, settings, existing.document_id)
        read_document(settings, existing)
        return existing, False
    identifier = f"DOC-{uuid4()}"
    staged = stage_path(settings, identifier)
    staged.parent.mkdir(parents=True, exist_ok=True)
    with staged.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        with factory.begin() as session:
            document = TransferDocument(document_id=identifier, transfer_id=transfer_id, document_type=document_type,
                document_source=document_source, file_name=f"{identifier}.pdf", original_file_name=filename,
                storage_path=storage_key(transfer_id, identifier), file_size=len(data), checksum_sha256=digest,
                uploaded_by="fictional-sample-generator" if sample_key else "api-service", version=version,
                is_sample=bool(sample_key), evaluation_only=evaluation_only, sample_key=sample_key, seed_key=seed_key)
            session.add(document)
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    # If the process stops here, PENDING metadata plus staged bytes are recoverable.
    result = finalize_document(factory, settings, identifier)
    if result.document_status != "READY":
        fail(503, "document_storage_failure", "Document could not be published safely")
    return result, True
