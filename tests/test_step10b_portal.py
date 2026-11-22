"""Step 10B portal tests use a webhook test double, never a UiPath claim."""
import secrets
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from backend.api import portal as portal_api
from backend.core.config import Settings
from backend.main import create_app
from backend.services.portal_investigations import PortalInvestigations, investigations

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
    review_script = (FLOW_SOURCE.parent / "scripts/record-review-input.js").read_text(encoding="utf-8")
    assert "reviewerReference:$vars.ValidateInput.output.reviewerReference" in review_script
    assert "reviewerReference:$vars.StartTransferInvestigation.output.reviewerReference" not in review_script


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
        assert body["startedAt"] <= body["lastUpdated"] < body["deadlineAt"]
        assert body["verificationStatus"] is None and body["auditUrl"] is None
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


def test_investigation_history_requires_session_and_has_empty_state(tmp_path):
    settings = configured_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        unauthorized = client.get("/api/portal/investigations")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["detail"]["code"] == "portal_authentication_required"

        login(client)
        history = client.get("/api/portal/investigations?limit=10&offset=0")
        assert history.status_code == 200
        assert history.headers["cache-control"] == "no-store"
        assert history.json() == {"items": [], "total": 0, "limit": 10, "offset": 0}
        assert client.get("/api/portal/investigations?limit=0&offset=0").status_code == 422


def test_investigation_history_is_operator_scoped_newest_first_and_paginated(tmp_path):
    settings = configured_settings(tmp_path).model_copy(update={
        "portal_starts_per_minute": 20,
        "portal_user_max_active": 20,
        "portal_global_max_active": 20,
    })
    settings.data_dir.mkdir(parents=True)
    registry = PortalInvestigations(settings)
    own_rows = [
        registry.create("demo-operator", f"TRF-100{i + 1}", f"history-own-{i}")[0]
        for i in range(3)
    ]
    other = registry.create("different-operator", "TRF-1005", "history-other")[0]
    with registry.engine.begin() as connection:
        for index, row in enumerate(own_rows):
            values = {
                "created_at": 1_000.0 + index,
                "updated_at": 1_100.0 + index,
                "investigation_status": "COMPLETED",
                "review_status": "NOT_REQUIRED" if index == 0 else "APPROVED",
                "workflow_outcome": None if index == 0 else "REVIEWED_WITH_OPEN_EXCEPTIONS",
                "verification_status": None if index == 0 else "VERIFIED_DEMO_STATE",
                "transfer_completed": None if index == 0 else "false",
            }
            connection.execute(update(investigations).where(
                investigations.c.execution_request_id == row["execution_request_id"]
            ).values(**values))
        connection.execute(update(investigations).where(
            investigations.c.execution_request_id == other["execution_request_id"]
        ).values(investigation_status="COMPLETED", created_at=2_000.0))
    registry.engine.dispose()

    with TestClient(create_app(settings)) as client:
        login(client)
        first = client.get("/api/portal/investigations?limit=2&offset=0")
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["total"] == 3
        assert first_body["limit"] == 2 and first_body["offset"] == 0
        assert [item["executionRequestId"] for item in first_body["items"]] == [
            own_rows[2]["execution_request_id"], own_rows[1]["execution_request_id"],
        ]
        assert all(item["transferId"] != "TRF-1005" for item in first_body["items"])
        assert first_body["items"][0]["verificationStatus"] == "VERIFIED_DEMO_STATE"

        second = client.get("/api/portal/investigations?limit=2&offset=2")
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["total"] == 3 and len(second_body["items"]) == 1
        historical = second_body["items"][0]
        assert historical["executionRequestId"] == own_rows[0]["execution_request_id"]
        assert historical["workflowOutcome"] is None
        assert historical["verificationStatus"] is None
        assert historical["transferCompleted"] is None


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
            "documentEvidenceStatus": "AGENT_ANALYZE_FILES",
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
        assert pending["verificationStatus"] == "NOT_VERIFIED"
        assert pending["documentEvidenceStatus"] == "AGENT_ANALYZE_FILES"
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
        assert final["verificationStatus"] == "VERIFIED_DEMO_STATE"
        assert final["documentEvidenceStatus"] == "AGENT_ANALYZE_FILES"
        assert final["auditUrl"] == path + "/audit"
        audit = client.get(final["auditUrl"])
        assert audit.status_code == 200
        assert {item["eventType"] for item in audit.json()["items"]} == {
            "PLAN_PREVIEWED", "DEMO_REVIEW_RECORDED",
            "DEMO_DISPOSITION_EXECUTED" if outcome == "APPROVE" else "DEMO_DISPOSITION_REJECTED",
        }


def test_clean_portal_run_completes_without_human_review_or_plan_audit(tmp_path, monkeypatch):
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(portal_api, "send_webhook", lambda _s, _p: (True, "event-clean", None))
    with TestClient(create_app(settings)) as client:
        csrf = login(client)
        started = start(client, csrf, transfer_id="TRF-1001").json()
        created = client.post("/api/demo/runs/review", json={
            "transferId": "TRF-1001", "executionRequestId": started["executionRequestId"],
        }, headers={"Idempotency-Key": started["executionRequestId"]})
        assert created.status_code == 201
        run = created.json()
        reconciled = client.post(f"/api/demo/runs/{run['runId']}/reconcile", json={})
        assert reconciled.status_code == 201
        final = client.get("/api/portal/investigations/" + started["executionRequestId"]).json()
        assert final["investigationStatus"] == "COMPLETED"
        assert final["reviewStatus"] == "NOT_REQUIRED"
        assert final["workflowOutcome"] == "CLEAN"
        assert final["planId"] is None and final["auditUrl"] is None
        assert final["documentEvidenceStatus"] is None
        assert final["positionsUnchanged"] is True and final["transferCompleted"] is False


def test_server_deadline_not_browser_polling_marks_workflow_timed_out(tmp_path, monkeypatch):
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(portal_api, "send_webhook", lambda _s, _p: (True, "event-timeout", None))
    with TestClient(create_app(settings)) as client:
        csrf = login(client)
        started = start(client, csrf).json()
        registry = client.app.state.portal_investigations
        with registry.engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE portal_investigations SET deadline_at = 0 WHERE execution_request_id = ?",
                (started["executionRequestId"],),
            )
        final = client.get("/api/portal/investigations/" + started["executionRequestId"]).json()
        assert final["investigationStatus"] == "TIMED_OUT"
        assert final["reviewStatus"] == "TIMED_OUT"
        assert "configured deadline" in final["errorSummary"]


@pytest.mark.parametrize("source_version", [1, 2])
def test_registry_upgrade_preserves_existing_tracking_row(tmp_path, source_version):
    settings = configured_settings(tmp_path)
    settings.data_dir.mkdir(parents=True)
    registry = PortalInvestigations(settings)
    row, created = registry.create("demo-operator", "TRF-1002", "migration-test-key")
    assert created is True
    registry.engine.dispose()
    database = settings.data_dir / "portal" / "transferiq.db"
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE portal_investigations DROP COLUMN document_evidence_status")
        if source_version == 1:
            connection.execute("ALTER TABLE portal_investigations DROP COLUMN verification_status")
        connection.execute(f"PRAGMA user_version={source_version}")
    upgraded = PortalInvestigations(settings)
    persisted = upgraded.read(row["execution_request_id"], "demo-operator")
    assert persisted["executionRequestId"] == row["execution_request_id"]
    assert persisted["documentEvidenceStatus"] is None
    assert persisted["verificationStatus"] is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
