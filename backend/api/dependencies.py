import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def fail(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def require_api_key(request: Request, supplied: Annotated[str | None, Security(api_key_header)]):
    expected = request.app.state.settings.api_key.get_secret_value()
    if not expected:
        fail(503, "authentication_not_configured", "Set API_KEY before accessing protected operations")
    if not supplied or not secrets.compare_digest(supplied.encode(), expected.encode()):
        fail(401, "unauthorized", "A valid X-API-Key header is required")


def pagination(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return {"limit": limit, "offset": offset}


DatabaseSession = Annotated[Session, Depends(get_session)]
Pagination = Annotated[dict, Depends(pagination)]
