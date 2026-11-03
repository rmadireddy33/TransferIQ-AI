from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.core.config import Settings
from backend.main import create_app
from backend.models.entities import AuditEvent, IdempotencyRecord, Transfer


@pytest.fixture
def client(client, auth):
    # Business API regression tests authenticate; public-access tests use a raw client.
    client.headers.update(auth)
    return client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "fictionalDemo": True}


@pytest.mark.parametrize("path,total", [
    ("/api/clients", 2), ("/api/firms", 2), ("/api/securities", 7), ("/api/transfers", 1),
    ("/api/delivering/accounts/ACC-SRC-001/positions", 7),
    ("/api/receiving/accounts/ACC-DST-001/positions", 7),
    ("/api/transfers/TRF-1001/assets", 7),
])
def test_lists(client, path, total):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["total"] == total
    assert len(response.json()["items"]) == total


@pytest.mark.parametrize("path,field,identifier", [
    ("/api/clients/CLI-001", "clientId", "CLI-001"),
    ("/api/accounts/ACC-SRC-001", "accountId", "ACC-SRC-001"),
    ("/api/transfers/TRF-1001", "transferId", "TRF-1001"),
    ("/api/securities/SEC-001", "securityId", "SEC-001"),
])
def test_lookup(client, path, field, identifier):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()[field] == identifier


def test_matching_staging_is_not_custody(client):
    source = client.get("/api/delivering/accounts/ACC-SRC-001/positions").json()
    destination = client.get("/api/receiving/accounts/ACC-DST-001/positions").json()
    assert destination["settledHoldings"] is False
    assert destination["positionKind"] == "RECEIVING_TRANSFER_STAGING"
    assert {x["securityId"]: Decimal(x["quantity"]) for x in source["items"]} == {
        x["securityId"]: Decimal(x["quantity"]) for x in destination["items"]}
    assert source["items"][4]["quantity"] == "18.00000001"
    assert all(x["transferId"] == "TRF-1001" for x in destination["items"])


def test_transfer_creation(client, auth, transfer_payload, app):
    before = client.get("/api/delivering/accounts/ACC-SRC-001/positions").json()
    response = client.post("/api/transfers", headers=auth, json=transfer_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["simulatedAcatsControlNumber"] is None
    assert body["createdAt"].endswith("Z")
    assert body["updatedAt"].endswith("Z")
    assert client.get(response.headers["Location"]).json() == body
    assert client.get(f"/api/transfers/{body['transferId']}/assets").json()["total"] == 0
    assert client.get("/api/delivering/accounts/ACC-SRC-001/positions").json() == before
    with app.state.session_factory() as session:
        event = session.scalar(select(AuditEvent).where(AuditEvent.transfer_id == body["transferId"]))
        assert event.action == "TRANSFER_CREATED"
        assert event.created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("patch", [
    {"clientId": "missing"}, {"sourceAccountId": "missing"}, {"receivingFirmId": "missing"},
    {"sourceAccountId": "ACC-SRC-002"}, {"destinationAccountId": "ACC-DST-002"},
    {"deliveringFirmId": "FIRM-NORTHSTAR"}, {"sourceAccountId": "ACC-DST-001"},
    {"transferType": "OTHER"}, {"status": "COMPLETED"}, {"clientId": ""},
])
def test_invalid_transfer(client, auth, transfer_payload, patch):
    response = client.post("/api/transfers", headers=auth, json={**transfer_payload, **patch})
    assert response.status_code == 422
    assert "detail" in response.json()
    assert client.get("/api/transfers").json()["total"] == 1


def test_required_fields(client, auth):
    assert client.post("/api/transfers", headers=auth, json={}).status_code == 422


def test_invalid_roles(client, auth, transfer_payload):
    reversed_route = {**transfer_payload, "deliveringFirmId": "FIRM-NORTHSTAR",
                      "receivingFirmId": "FIRM-SUMMIT", "sourceAccountId": "ACC-DST-001",
                      "destinationAccountId": "ACC-SRC-001"}
    assert client.post("/api/transfers", headers=auth, json=reversed_route).status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "incorrect"}])
def test_unauthorized_creation(client, auth, transfer_payload, headers):
    client.headers.pop('X-API-Key', None)
    assert client.post("/api/transfers", headers=headers, json=transfer_payload).status_code == 401
    assert client.get("/api/transfers", headers=auth).json()["total"] == 1


def test_unconfigured_auth_fails_closed(tmp_path, transfer_payload):
    with TestClient(create_app(Settings(data_dir=tmp_path, api_key=""))) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/api/transfers", json=transfer_payload).status_code == 503


def test_idempotency(client, auth, transfer_payload, app):
    headers = {**auth, "Idempotency-Key": "pytest-transfer-1"}
    first = client.post("/api/transfers", headers=headers, json=transfer_payload)
    second = client.post("/api/transfers", headers=headers, json=transfer_payload)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json() == second.json()
    assert client.post("/api/transfers", headers=headers,
                       json={**transfer_payload, "transferType": "PARTIAL"}).status_code == 409
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Transfer)) == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1


def test_failed_create_does_not_claim_key(client, auth, transfer_payload):
    headers = {**auth, "Idempotency-Key": "retry-valid-input"}
    assert client.post("/api/transfers", headers=headers,
                       json={**transfer_payload, "clientId": "missing"}).status_code == 422
    assert client.post("/api/transfers", headers=headers, json=transfer_payload).status_code == 201


@pytest.mark.parametrize("path", ["/api/clients/missing", "/api/accounts/missing",
    "/api/transfers/missing", "/api/transfers/missing/assets", "/api/securities/missing",
    "/api/delivering/accounts/missing/positions", "/api/receiving/accounts/missing/positions"])
def test_not_found(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_pagination(client):
    data = client.get("/api/securities?limit=2&offset=2").json()
    assert data["total"] == 7 and data["limit"] == 2 and data["offset"] == 2
    assert [x["securityId"] for x in data["items"]] == ["SEC-003", "SEC-004"]
    assert client.get("/api/securities?limit=101").status_code == 422
    assert client.get("/api/securities?offset=-1").status_code == 422
    assert client.get("/api/securities?offset=100").json()["items"] == []


def test_receiving_account_filter(client):
    assert client.get("/api/receiving/accounts/ACC-DST-002/positions").json()["total"] == 0
    assert client.get("/api/receiving/accounts/ACC-DST-002/positions?transferId=TRF-1001").status_code == 422
    assert client.get("/api/receiving/accounts/ACC-DST-001/positions?transferId=TRF-1001").json()["total"] == 7
    assert client.get("/api/delivering/accounts/ACC-DST-001/positions").status_code == 422
    assert client.get("/api/receiving/accounts/ACC-SRC-001/positions").status_code == 422


def test_swagger(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
    assert spec["paths"]["/api/transfers"]["post"]["security"] == [{"APIKeyHeader": []}]
