# Maestro Automate setup

Use [credential-free judge instructions](ZERO_CREDENTIAL_DEMO.md). They supersede the earlier private HTTP connection setup.

The existing solution is `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation.uipx`; its project is the nested `TransferIQ_Reconciliation/` directory. Open `TransferIQ_Reconciliation.flow` there with the UiPath Maestro visual designer. This is an Automate Flow with its existing `.maestro_automate` marker and Lite runtime profile, not BPMN or Case.

Authoritative source remains `.flow-sdk/TransferIQ_Reconciliation.flow.ts` and `.flow-sdk/scripts/*.js`. Run `scripts/build-maestro.ps1` to check, compile, format and validate. Preserve any independent visual designer edits before rebuilding from source.

The 28-node/27-edge Flow takes `transferId` from Manual Trigger. `CreateDemoRun` creates an isolated synthetic execution; `ValidateDemoRun` checks its returned runId and selected transfer. Four downstream HTTP nodes retrieve transfer/source/staging context and invoke reconciliation using real previous-node outputs. All five use Manual HTTP authentication without connection bindings or secrets. `NormalizeReconciliation` validates real backend results and exposes `demoRunId`, `reconciliationRunId`, counters, exceptions and workflow outcome. Decisions fail closed on invalid responses.

See [actual cloud execution evidence and Studio Web instructions](MAESTRO_LIVE_EXECUTION.md). TRF-1001/TRF-1002/TRF-1005 completed with expected outcomes; unknown-ID attempts safely failed with HTTP 429, which masks the expected 422 validator response in cloud traces. Historical counts in `MAESTRO_STEP5_TEST_CASES.md` describe the earlier increment. No IXP, agent, human task or financial correction node is included.
