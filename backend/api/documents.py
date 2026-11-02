from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import select

from backend.api.dependencies import DatabaseSession, Pagination, fail, require_api_key
from backend.api.routes import page
from backend.models.documents import DocumentSource, DocumentType, TransferDocument
from backend.models.entities import Transfer
from backend.schemas.contracts import ErrorResponse, Page
from backend.schemas.documents import DocumentResponse
from backend.services.document_storage import read_document, save_document
from backend.services.transfers import require_record

router = APIRouter(tags=["Documents"], dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
               413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})


@router.post("/api/transfers/{transferId}/documents", response_model=DocumentResponse, status_code=201)
def upload_document(transferId: str, request: Request, response: Response,
                    file: Annotated[UploadFile, File()], documentType: Annotated[DocumentType, Form()],
                    documentSource: Annotated[DocumentSource, Form()]):
    if file.content_type != "application/pdf":
        fail(415, "unsupported_file", "Upload Content-Type must be application/pdf")
    with request.app.state.session_factory() as session:
        require_record(session, Transfer, transferId)
    settings = request.app.state.settings
    data = file.file.read(settings.max_document_bytes + 1)
    document, _ = save_document(request.app.state.session_factory, settings, transferId, data,
                                file.filename, documentType, documentSource)
    response.headers["Location"] = f"/api/documents/{document.document_id}"
    return document


@router.get("/api/transfers/{transferId}/documents", response_model=Page[DocumentResponse])
def list_documents(transferId: str, session: DatabaseSession, bounds: Pagination,
                   documentType: DocumentType | None = None, includeEvaluation: bool = False):
    require_record(session, Transfer, transferId)
    statement = select(TransferDocument).where(TransferDocument.transfer_id == transferId)
    if documentType:
        statement = statement.where(TransferDocument.document_type == documentType)
    if not includeEvaluation:
        statement = statement.where(TransferDocument.evaluation_only.is_(False))
    return page(session, statement.order_by(TransferDocument.created_at, TransferDocument.document_id), bounds)


@router.get("/api/documents/{documentId}", response_model=DocumentResponse)
def metadata(documentId: str, session: DatabaseSession):
    return require_record(session, TransferDocument, documentId)


def download_response(request, document):
    data = read_document(request.app.state.settings, document)
    return Response(content=data, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{document.file_name}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
        "X-Checksum-SHA256": document.checksum_sha256})


@router.get("/api/documents/{documentId}/download", response_class=Response,
            responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}})
def download(documentId: str, request: Request, session: DatabaseSession):
    return download_response(request, require_record(session, TransferDocument, documentId))


@router.get("/api/transfers/{transferId}/documents/{documentId}/download", response_class=Response,
            responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}})
def scoped_download(transferId: str, documentId: str, request: Request, session: DatabaseSession):
    require_record(session, Transfer, transferId)
    document = require_record(session, TransferDocument, documentId)
    if document.transfer_id != transferId:
        fail(404, "not_found", "Document was not found for this transfer")
    return download_response(request, document)
