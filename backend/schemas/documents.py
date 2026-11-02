from datetime import datetime

from backend.models.documents import DocumentSource, DocumentType
from backend.schemas.contracts import Contract


class DocumentResponse(Contract):
    document_id: str
    transfer_id: str
    document_type: DocumentType
    document_source: DocumentSource
    file_name: str
    original_file_name: str
    mime_type: str
    file_size: int
    checksum_sha256: str
    uploaded_by: str
    uploaded_at: datetime
    document_status: str
    version: int
    created_at: datetime
    updated_at: datetime
    is_sample: bool
    evaluation_only: bool
