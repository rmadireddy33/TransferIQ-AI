"""Authenticated portal operator session and controlled Maestro trigger APIs."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Cookie, Header, Query, Request, Response, Security
from fastapi.security import APIKeyCookie
from pydantic import Field

from backend.api.dependencies import fail
from backend.schemas.contracts import Contract


router = APIRouter(prefix="/api/portal", tags=["Controlled portal operations"])
COOKIE = "transferiq_portal_session"
portal_cookie = APIKeyCookie(name=COOKIE, scheme_name="PortalOperatorSession", auto_error=False)


class LoginRequest(Contract):
    access_code: str = Field(min_length=1, max_length=512)


class InvestigationRequest(Contract):
    transfer_id: Literal["TRF-1001", "TRF-1002", "TRF-1003", "TRF-1004", "TRF-1005"]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _session_token(settings, operator_id: str, csrf: str) -> str:
    payload = _b64(json.dumps({
        "sub": operator_id,
        "exp": int(time.time()) + settings.portal_session_ttl_minutes * 60,
        "csrf": csrf,
    }, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(settings.session_secret.get_secret_value().encode("utf-8"),
                         payload.encode("ascii"), hashlib.sha256).digest()
    return payload + "." + _b64(signature)


def _read_session(request: Request, token: str | None, csrf: str | None = None):
    settings = request.app.state.settings
    if not settings.portal_investigation_enabled:
        fail(503, "portal_investigation_disabled", "Controlled portal investigation is not configured")
    if not token:
        fail(401, "portal_authentication_required", "Sign in as an authorized demo operator")
    try:
        payload, supplied_signature = token.split(".", 1)
        expected = hmac.new(settings.session_secret.get_secret_value().encode("utf-8"),
                            payload.encode("ascii"), hashlib.sha256).digest()
        if not secrets.compare_digest(_unb64(supplied_signature), expected):
            raise ValueError
        claims = json.loads(_unb64(payload))
        if claims.get("sub") != settings.portal_operator_id or int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError
        if csrf is not None and not secrets.compare_digest(str(claims.get("csrf", "")), csrf):
            fail(403, "csrf_validation_failed", "Portal session verification failed")
        return claims
    except Exception as exc:
        if getattr(exc, "status_code", None):
            raise
        fail(401, "portal_session_invalid", "Portal operator session is invalid or expired")


def _manager(request: Request):
    manager = getattr(request.app.state, "portal_investigations", None)
    if manager is None:
        fail(503, "portal_investigation_disabled", "Controlled portal investigation is not configured")
    return manager


def send_webhook(settings, payload: dict):
    """One bounded request, deliberately without automatic retries."""
    url = settings.uipath_webhook_url.get_secret_value()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        settings.uipath_webhook_auth_header_name: settings.uipath_webhook_auth_header_value.get_secret_value(),
    }
    with httpx.Client(timeout=settings.uipath_webhook_timeout_seconds, follow_redirects=False) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        if response.status_code in (401, 403):
            return False, None, "UiPath rejected the configured webhook authentication."
        return False, None, f"UiPath webhook returned HTTP {response.status_code}."
    try:
        event_id = response.json().get("webhookEventId")
    except (ValueError, AttributeError):
        event_id = None
    if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
        return False, None, "UiPath webhook acceptance response was malformed."
    return True, event_id, None


@router.get("/session")
def session_status(request: Request,
                   token: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    settings = request.app.state.settings
    if not settings.portal_investigation_enabled:
        return {"enabled": False, "authorized": False, "operatorId": None}
    try:
        claims = _read_session(request, token)
    except Exception:
        return {"enabled": True, "authorized": False, "operatorId": None}
    return {"enabled": True, "authorized": True, "operatorId": claims["sub"]}


@router.post("/session")
def login(data: LoginRequest, request: Request, response: Response):
    settings = request.app.state.settings
    if not settings.portal_investigation_enabled:
        fail(503, "portal_investigation_disabled", "Controlled portal investigation is not configured")
    expected = settings.portal_operator_access_key.get_secret_value()
    if not secrets.compare_digest(data.access_code.encode("utf-8"), expected.encode("utf-8")):
        fail(401, "portal_login_failed", "Operator access code is invalid")
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        COOKIE, _session_token(settings, settings.portal_operator_id, csrf),
        max_age=settings.portal_session_ttl_minutes * 60,
        secure=settings.app_env == "production", httponly=True, samesite="strict", path="/api/portal",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": True, "authorized": True, "operatorId": settings.portal_operator_id, "csrfToken": csrf}


@router.post("/investigations", status_code=201)
def start_investigation(
    data: InvestigationRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=16, max_length=128,
                                           pattern=r"^[A-Za-z0-9._:-]+$")],
    token: Annotated[str | None, Security(portal_cookie)] = None,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    claims = _read_session(request, token, csrf)
    manager = _manager(request)
    row, created = manager.create(claims["sub"], data.transfer_id, idempotency_key)
    if created:
        payload = {"transferId": data.transfer_id,
                   "executionRequestId": row["execution_request_id"], "enableIXP": False}
        try:
            accepted, event_id, error = send_webhook(request.app.state.settings, payload)
        except httpx.TimeoutException:
            accepted, event_id, error = False, None, "UiPath webhook request timed out; delivery is uncertain and was not retried."
        except httpx.HTTPError:
            accepted, event_id, error = False, None, "UiPath webhook is unavailable; the request was not retried."
        manager.set_trigger_result(row["execution_request_id"], accepted, event_id, error)
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return manager.read(row["execution_request_id"], claims["sub"])


@router.get("/investigations")
def list_investigations(
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    token: Annotated[str | None, Security(portal_cookie)] = None,
):
    claims = _read_session(request, token)
    response.headers["Cache-Control"] = "no-store"
    return _manager(request).list_for_operator(claims["sub"], limit, offset)


@router.get("/investigations/{executionRequestId}")
def get_investigation(
    executionRequestId: str,
    request: Request,
    response: Response,
    token: Annotated[str | None, Security(portal_cookie)] = None,
):
    if not executionRequestId.startswith("PEX-") or len(executionRequestId) != 36:
        fail(404, "not_found", "Investigation was not found")
    claims = _read_session(request, token)
    response.headers["Cache-Control"] = "no-store"
    return _manager(request).read(executionRequestId, claims["sub"])
