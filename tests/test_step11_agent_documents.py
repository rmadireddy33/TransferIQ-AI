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


API_WORKFLOW = FLOW.parents[1] / "TransferIQ_Document_Retrieval" / "Workflow.json"


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
    attachment = definition["inputSchema"]["properties"]["agentDocument"]
    assert attachment == {"$ref": "#/definitions/job-attachment"}
    assert definition["inputSchema"]["properties"]["SerializeInvestigationContext__output"] == {"type": "string"}
    assert definition["inputSchema"]["definitions"]["job-attachment"]["x-uipath-resource-kind"] == "JobAttachment"
    assert "documentEvidence" in definition["outputSchema"]["required"]
    user_message = next(message for message in definition["messages"] if message["role"] == "user")
    variable_tokens = [token["rawString"] for token in user_message["contentTokens"]
                       if token["type"] == "variable"]
    assert variable_tokens == [
        "input.SerializeInvestigationContext__output",
        "input.agentDocument",
    ]
    assert "{{input.SerializeInvestigationContext__output}}" in user_message["content"]
    assert "{{input.agentDocument}}" in user_message["content"]
    assert all("{{" not in token.get("rawString", "")
               for token in user_message["contentTokens"] if token["type"] == "simpleText")
    # The Flow node resolves upstream values before starting the agent job. The
    # sidecar uses input.* tokens, but using those tokens in the Flow node made
    # Maestro pass their names through as literal prompt text at runtime.
    assert "{{ $vars.SerializeInvestigationContext.output }}" in agent["inputs"]["userPrompt"]
    assert "{{ $vars.agentDocument }}" in agent["inputs"]["userPrompt"]
    assert "{{input." not in agent["inputs"]["userPrompt"]


def test_phase_b_uses_real_api_workflow_file_conversion_and_fail_closed_fallback():
    flow = json.loads(FLOW.read_text())
    by_id = {node["id"]: node for node in flow["nodes"]}
    retrieval = by_id["RetrieveCorporateActionDocument"]
    assert retrieval["type"].startswith("uipath.core.api-workflow.")
    assert retrieval["inputs"]["runId"]["expression"] == "$vars.ValidateDemoRun.output.runId"
    assert retrieval["inputs"]["transferId"]["expression"] == "$vars.ValidateInput.output.transferId"
    assert by_id["TransferInvestigationAgent"]["inputs"]["agentInputVariables"][1] == {
        "id": "agentDocument", "type": "object", "binding": "=js:$vars.agentDocument"
    }
    assert "object($vars.agentDocument)" in by_id["PrepareInvestigationContext"]["inputs"]["script"]
    assert "DOCUMENT_RETRIEVAL_FAILED" in by_id["DocumentRetrievalUnavailable"]["inputs"]["script"]

    workflow = json.loads(API_WORKFLOW.read_text())
    sequence = workflow["do"][0]["Sequence_1"]["do"]
    serialized = json.dumps(sequence)
    assert serialized.count('"call": "UiPath.Http"') == 2
    assert "$helpers.file.base64ToFile" in serialized
    assert "Object.entries($context.outputs.Base64ToFile_1.output.Metadata || {})" in serialized
    assert "String(value)" in serialized
    assert "corporate-action-notice.pdf" in serialized
    assert "contentBase64" in serialized
    assert "UIPATH_WEBHOOK" not in serialized and "API_KEY" not in serialized


def test_canonical_document_retrieval_bindings_are_complete_and_in_solution():
    flow = json.loads(FLOW.read_text())
    assert len(flow["nodes"]) == 81
    assert len(flow["edges"]) == 86

    retrieval = next(node for node in flow["nodes"]
                     if node["id"] == "RetrieveCorporateActionDocument")
    definition = next(item for item in flow["definitions"]
                      if item["nodeType"] == retrieval["type"])
    binding_key = definition["model"]["bindings"]["resourceKey"]
    assert binding_key == "b41e40a5-172f-465d-8aee-01d75ea8e906"

    rows = {
        (row["name"], row["propertyAttribute"]): row
        for row in flow["bindings"]
        if row.get("resource") == "process" and row.get("resourceKey") == binding_key
    }
    assert set(rows) == {("name", "name"), ("folderPath", "folderPath")}
    assert rows[("name", "name")]["default"] == "TransferIQ_Document_Retrieval"
    assert rows[("folderPath", "folderPath")]["default"] == "solution_folder"
    assert all(row["resourceSubType"] == "Api" for row in rows.values())


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

