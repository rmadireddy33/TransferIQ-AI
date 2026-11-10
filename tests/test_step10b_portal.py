"""Step 10B portal tests use a webhook test double, never a UiPath claim."""
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api import portal as portal_api
from backend.core.config import Settings
from backend.main import create_app

FLOW_SOURCE = Path(__file__).parents[1] / "maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/TransferIQ_Reconciliation.flow.ts"


def configured_settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "step10b",
        api_key=secrets.token_urlsafe(32),
        portal_investigation_enabled=True,
        portal_operator_access_key="test-operator-access-key",
        session_secret="test-session-secret-that-is-long-enough-123456",
        uipath_webhook_url="https://example.invalid/uipath-webhook",
        uipath_webhook_auth_header_name="X-TransferIQ-Webhook",
        uipath_webhook_auth_header_value="test-webhook-value",
    )


def login(client):
    response = client.post("/api/portal/session", json={"accessCode": "test-operator-access-key"})
    assert response.status_code == 200, response.text
    return response.json()["csrfToken"]


def start(client, csrf, transfer_id="TRF-1002", key=None):
    return client.post("/api/portal/investigations", json={"transferId": transfer_id}, headers={
        "X-CSRF-Token": csrf, "Idempotency-Key": key or uuid4().hex,
    })


def test_public_portal_stays_available_while_trigger_is_disabled(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/demo/transfers").status_code == 200
        assert client.get("/api/portal/session").json() == {
            "enabled": False, "authorized": False, "operatorId": None,
        }
        assert client.post("/api/portal/investigations", json={"transferId": "TRF-1002"},
                           headers={"Idempotency-Key": uuid4().hex}).status_code == 503


def test_flow_source_preserves_manual_root_and_adds_strict_webhook_contract():
    source = FLOW_SOURCE.read_text(encoding="utf-8")
    assert '.triggerId("StartTransferInvestigation")' in source
    assert '.trigger(manual()' in source
    assert '.entryPoint("PortalWebhook", onEvent(HttpWebhook' in source
    assert "!/^PEX-[0-9a-f]{32}$/.test(input.executionRequestId)" in source
    assert "input.enableIXP !== false" in source
    assert "executionRequestId: $vars.ValidateInput.output.executionRequestId" in source


def test_authorized_start_is_persisted_idempotent_and_secret_free(tmp_path, monkeypatch):
    settings = configured_settings(tmp_path)
    calls = []

    def accepted(actual_settings, payload):
        calls.append((actual_settings, payload))
        return True, "event-test-1", None

    monkeypatch.setattr(portal_api, "send_webhook", accepted)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/portal/session", json={"accessCode": "wrong-value"}).status_code == 401
        csrf = login(client)
        key = uuid4().hex
        first = start(client, csrf, key=key)
        assert first.status_code == 201, first.text
        body = first.json()
        assert body["triggerStatus"] == "ACCEPTED"
        assert body["investigationStatus"] == "TRIGGERED"
        assert body["executionRequestId"].startswith("PEX-")
        assert calls[0][1] == {"transferId": "TRF-1002",
                               "executionRequestId": body["executionRequestId"], "enableIXP": False}
        assert settings.uipath_webhook_auth_header_value.get_secret_value() not in first.text
        replay = start(client, csrf, key=key)
        assert replay.status_code == 200
        assert replay.json()["executionRequestId"] == body["executionRequestId"]
        assert len(calls) == 1
        assert start(client, csrf, key=uuid4().hex).status_code == 409
        tracked = client.get("/api/portal/investigations/" + body["executionRequestId"])
        assert tracked.status_code == 200 and tracked.json() == replay.json()

    # Registry survives an application restart.
    with TestClient(create_app(settings)) as client:
        csrf = login(client)
        tracked = client.get("/api/portal/investigations/" + body["executionRequestId"])
        assert tracked.status_code == 200
        assert tracked.json()["transferId"] == "TRF-1002"


def test_webhook_failure_is_recorded_without_retry(tmp_path, monkeypatch):
    settings = configured_settings(tmp_path)
    calls = []

    def rejected(_settings, payload):
        calls.append(payload)
        return False, None, "UiPath rejected the configured webhook authentication."

    monkeypatch.setattr(portal_api, "send_webhook", rejected)
    with TestClient(create_app(settings)) as client:
        csrf = login(client)
        response = start(client, csrf)
        assert response.status_code == 201
        assert response.json()["triggerStatus"] == "FAILED"
        assert response.json()["investigationStatus"] == "FAILED"
        assert response.json()["errorSummary"] == "UiPath rejected the configured webhook authentication."
        assert len(calls) == 1


@pytest.mark.parametrize("outcome,expected,review_status", [
    ("APPROVE", "REVIEWED_WITH_OPEN_EXCEPTIONS", "APPROVED"),
    ("REJECT", "REVIEW_REJECTED", "REJECTED"),
])
def test_portal_correlation_reaches_real_isolated_backend_and_final_audit(
        tmp_path, monkeypatch, outcome, expected, review_status):
    """Backend lifecycle is real; webhook/agent/human values are explicit test doubles."""
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(portal_api, "send_webhook", lambda _s, _p: (True, "event-test-2", None))
    with TestClient(create_app(settings)) as client:
        csrf = login(client)
        started = start(client, csrf).json()
        execution_id = started["executionRequestId"]
        created = client.post("/api/demo/runs/review", json={
            "transferId": "TRF-1002", "executionRequestId": execution_id,
        }, headers={"Idempotency-Key": execution_id})
        assert created.status_code == 201, created.text
        run = created.json()
        root = "/api/demo/runs/" + run["runId"]
        reconciliation = client.post(root + "/reconcile", json={}).json()
        plan_body = {
            "transferId": "TRF-1002",
            "reconciliationRunId": reconciliation["reconciliationRunId"],
            "agentInvestigationId": execution_id + ":TransferInvestigationAgent",
            "investigationSummary": "Explicit agent test double; not a live UiPath agent result.",
            "overallRiskLevel": "MEDIUM",
            "documentEvidenceStatus": "NOT_PROCESSED_IXP_DISABLED",
            "proposedActions": [{
                "exceptionId": item["exceptionId"], "securityId": item["securityId"],
                "evidenceReferences": item["evidenceReferences"],
                "disposition": "ACCEPT_VERIFIED_EXPLANATION" if item["resolutionStatus"] == "EXPLAINED"
                    else "ESCALATE_TO_TRANSFER_OPERATIONS",
            } for item in reconciliation["exceptions"]],
        }
        headers = {"X-Demo-Capability": run["reviewCapability"], "Idempotency-Key": execution_id}
        preview = client.post(root + "/resolution-plans/preview", json=plan_body, headers=headers)
        assert preview.status_code == 200, preview.text
        plan = preview.json()
        pending = client.get("/api/portal/investigations/" + execution_id).json()
        assert pending["investigationStatus"] == "AWAITING_HUMAN_REVIEW"
        assert pending["reviewStatus"] == "PENDING"
        assert "SEC-104" in {x["securityId"] for x in pending["unresolvedExceptions"]}
        path = root + "/resolution-plans/" + plan["planId"]
        binding = {"planVersion": plan["planVersion"], "planHash": plan["planHash"]}
        decision = {**binding, "reviewOutcome": outcome, "reviewerReference": "TEST-DOUBLE",
                    "reviewerComments": "Automated test only", "additionalInformation": "",
                    "reviewEventReference": "TEST-" + uuid4().hex}
        assert client.post(path + "/decision", json=decision, headers=headers).status_code == 200
        assert client.post(path + "/execute", json=binding, headers=headers).status_code == 200
        final = client.get("/api/portal/investigations/" + execution_id).json()
        assert final["investigationStatus"] == "COMPLETED"
        assert final["reviewStatus"] == review_status
        assert final["workflowOutcome"] == expected
        assert final["positionsUnchanged"] is True and final["transferCompleted"] is False
        shortage = next(x for x in final["unresolvedExceptions"] if x["securityId"] == "SEC-104")
        assert shortage["difference"] == "-20"
        assert final["auditReference"] == plan["planId"]
