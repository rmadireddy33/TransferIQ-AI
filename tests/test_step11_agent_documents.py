"""Step 11 contracts and explicit test doubles; these are not live UiPath extraction tests."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import create_app
from backend.schemas.resolution import PlanPreview
from tests.test_maestro_contract import FLOW, collect
from tests.test_step8_agent import mock_agent, run_graph


@pytest.fixture(scope="module")
def trf1002(tmp_path_factory):
    with TestClient(create_app(Settings(data_dir=tmp_path_factory.mktemp("step11")))) as client:
        return collect(client, "TRF-1002")


def test_canonical_flow_has_only_the_builtin_analyze_files_tool():
    flow = json.loads(FLOW.read_text())
    agent = next(node for node in flow["nodes"] if node["id"] == "TransferInvestigationAgent")
    tools = [node for node in flow["nodes"] if node["type"].startswith("uipath.agent.resource.tool.")]
    assert [node["type"] for node in tools] == ["uipath.agent.resource.tool.builtin.analyzefiles"]
    assert any(edge["sourceNodeId"] == agent["id"] and edge["targetNodeId"] == tools[0]["id"]
               for edge in flow["edges"])
    assert "call Analyze Files exactly once" in agent["inputs"]["systemPrompt"]
    assert "corporate_action_pdf" in agent["inputs"]["userPrompt"]

    source = FLOW.parent / agent["inputs"]["source"]
    definition = json.loads((source / "agent.json").read_text())
    attachment = definition["inputSchema"]["properties"]["ValidateInput__output__corporateActionPdf"]
    assert attachment == {"$ref": "#/definitions/job-attachment"}
    assert definition["inputSchema"]["definitions"]["job-attachment"]["x-uipath-resource-kind"] == "JobAttachment"
    assert "documentEvidence" in definition["outputSchema"]["required"]


def test_analyze_files_test_double_is_independently_validated(trf1002):
    result = run_graph("TRF-1002", trf1002, localTransport=True,
        corporateActionPdf={"ID": "EXPLICIT_TEST_FILE"},
        agentTestDouble=mock_agent(trf1002, analyze_file=True))["result"]
    assert result["documentEvidenceStatus"] == "AGENT_ANALYZE_FILES"
    assert result["documentEvidence"]["validationStatus"] == "VERIFIED"
    assert result["documentEvidence"]["extractionMethod"] == "AGENT_ANALYZE_FILES"
    assert result["unresolvedExceptions"][0]["securityId"] == "SEC-104"
    assert result["unresolvedExceptions"][0]["difference"] == "-20"
    assert result["sourcePositions"] == trf1002["GetDeliveringPositions"]["body"]["items"]
    assert result["receivingStagingPositions"] == trf1002["GetReceivingPositions"]["body"]["items"]


def test_document_mismatch_becomes_review_required_without_financial_change(trf1002):
    agent = mock_agent(trf1002, analyze_file=True)
    agent["documentEvidence"]["extractedFields"]["splitNumerator"] = 3
    result = run_graph("TRF-1002", trf1002, localTransport=True,
        corporateActionPdf={"ID": "EXPLICIT_TEST_FILE"}, agentTestDouble=agent)["result"]
    evidence = result["documentEvidence"]
    assert evidence["validationStatus"] == "REVIEW_REQUIRED"
    assert any("splitNumerator" in item for item in evidence["discrepancies"])
    assert result["correctionsApplied"] == 0 and result["transferCompleted"] is False
    assert result["unresolvedExceptions"][0]["difference"] == "-20"


def test_missing_document_identifier_becomes_review_required(trf1002):
    agent = mock_agent(trf1002, analyze_file=True)
    agent["documentEvidence"]["documentId"] = None
    agent["documentEvidence"]["missingFields"] = ["documentId"]
    result = run_graph("TRF-1002", trf1002, localTransport=True,
        corporateActionPdf={"ID": "EXPLICIT_TEST_FILE"}, agentTestDouble=agent)["result"]
    assert result["documentEvidence"]["validationStatus"] == "REVIEW_REQUIRED"
    assert "documentId" in result["documentEvidence"]["missingFields"]


@pytest.mark.parametrize("status", ["NOT_PROCESSED_IXP_DISABLED", "API_ONLY", "AGENT_ANALYZE_FILES"])
def test_resolution_preview_accepts_only_supported_document_routes(status):
    payload = dict(transferId="TRF-1002", reconciliationRunId="REC-test",
        agentInvestigationId="TIQ-test:TransferInvestigationAgent", investigationSummary="Synthetic test",
        overallRiskLevel="MEDIUM", documentEvidenceStatus=status,
        proposedActions=[dict(exceptionId="EX-test", securityId="SEC-103",
            disposition="ACCEPT_VERIFIED_EXPLANATION", evidenceReferences=["CA-2026-081"])])
    assert PlanPreview.model_validate(payload).document_evidence_status == status

