# Existing IXP model deployment status

## Requested dedicated folder: created; deployment rejected

On 2026-11-05 (America/New_York), the user requested creation of the top-level, non-personal folder `transferiq-corporateactionextractor` and deployment there. `uip or folders create transferiq-corporateactionextractor --output json` returned `FolderCreated`. Actual folder identifiers are retained in ignored `data/verification/ixp-deployment/folder-create.json`.

Version 3 was reverified as published and tagged live; the project had no existing deployments. `uip ixp deployments create <resolved-project-name> --version 3 --folder-key <new-folder-key> --title TransferIQ-CorporateActionExtractor --output json` returned exit 1, HTTP 403, `permission_denied`, `[IxpUpstreamError]`, `RetryWillNotFix`. The actual response is in `create-nonpersonal.json` in the same evidence directory. No deployment name was returned.

The subsequent effective-permissions read for this exact new folder returned Folder Administrator and `IXPModels.Create`, `IXPModels.View`, `IXPModels.Edit`, and `IXPModels.Delete`. The subsequent `ixp deployments list` still returned an empty array (saved as `list-after-nonpersonal.json`). Thus the folder exists, but no deployment succeeded. The exact denied upstream permission or scope is not identified by the generic 403; do not claim that IXPModels.Create is missing. No retry or role modification was performed. Maestro discovery remains unverified. The personal workspace was not used in this attempt.

## Latest target constraint and permission recheck

The user explicitly excluded the personal workspace as a deployment target. The earlier workspace selection below is historical only; do not reuse it or its debug subfolders for deployment. The subsequently selected dedicated target is recorded above.

Read-only recheck: login remains valid in the same tenant. `uip or roles user-permissions list <connected-user> --folder-path Development --output json` and the equivalent command for `DemoFolder` both returned Success and effective `IXPModels.Create`, `IXPModels.View`, `Jobs.Create`, and `Logs.View` permissions. Both folders include the Orchestrator Folder Administrator role. No deployment or permission mutation was performed during this recheck. These results do not establish the cause of the earlier 403.

`uip admin authorization check-access <connected-user-id> --service reinfer --output json` also confirmed tenant-scoped IXP Package Admin and IXP Package Reader roles, granted directly and inherited from the Administrators group (resolved with `uip admin groups get`). The tenant binding is the connected tenant. These current grants supersede the earlier uncertainty about whether package roles were present; they do not prove a successful deployment.

Verified on 2026-11-04 (America/New_York). Deployment is blocked; no successful folder deployment or Flow discovery is claimed.

## Observed CLI results

- `uip login status --output json` and `uip login tenant list --output json`: saved user login is valid; the selected tenant is the only returned tenant.
- `uip ixp projects list --output json`: exactly one project matched `TransferIQ-CorporateActionExtractor`. The internal Name was resolved from the response, not constructed from the title.
- `uip ixp projects list-models <resolved-project-name> --output json`: Version 3 exists, `Pinned: true`, and tag `live` points to Version 3. No publish operation was needed.
- `uip or folders list --limit 500 --output json`: nine accessible folders, no further page. The personal workspace key matches `Data.folderKey` in the existing Step 7 Flow debug evidence. The similarly named debug subfolders were not selected by name guessing.
- `uip ixp deployments list <resolved-project-name> --output json`: empty array before the attempt.
- `uip ixp deployments create <resolved-project-name> --version 3 --folder-key <verified-workspace-key> --title TransferIQ-CorporateActionExtractor --output json`: exit 1, HTTP 403, `AuthenticationError`, `permission_denied`, `[IxpUpstreamError]`, `RetryWillNotFix`. No deployment name was returned. Actual response retained in ignored `data/verification/ixp-deployment/create.json`.
- `uip login status --detailed --output json`: includes Reinfer, DocumentUnderstanding, OrchestratorApiUserAccess and RCS.FolderAuthorization scopes. These scopes do not prove folder-role permissions.

Stopped after the denial as requested. No retry, project creation, unrelated deployment upgrade/delete, Flow change, or financial-engine change was performed. Post-deployment listing and Maestro registry discovery remain blocked/not run. Application tests were not run because application code was unchanged.

The CLI initially was absent from PATH; the existing `%APPDATA%/npm/uip.cmd` worked (version 1.205.0). Its automatic extension update reported Codex/Copilot skill updates succeeded and a Claude skill update failed because the Claude CLI was absent; the IXP read commands still succeeded.

## Access required

UiPath documents **IXP Models - Create** in the target Orchestrator folder for folder deployment. IXP package creation also uses **Packages - Write**; package access is assigned through IXP package roles. The generic 403 did not identify which individual permission was denied, so the exact missing grant is not established. An administrator must inspect the connected user's effective folder and IXP package permissions; do not treat token scopes as proof of authorization.

Sources: [Consuming models via Flow](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/consuming-models-via-flow), [UCD roles and permissions](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/roles-and-permissions-unstructured-documents-projects).

## Resume after access is corrected

1. Resolve the upstream 403 before another write. Reuse the dedicated folder created above, resolving its key from UiPath or saved actual evidence. Re-read model versions and deployments, then create the requested Version 3 folder deployment if absent. Retrieve the actual DeploymentName and FolderKey from UiPath and verify them in the deployment list. Do not use the historical personal-workspace key.
2. Follow the installed Maestro Flow skill: refresh the Flow registry and search `uipath.ixp` to verify discovery. Do not infer discovery from publication alone.
3. Preserve/download the current designer artifact. Replace the `CorporateActionExtractor` setup-stop Script with the discovered Extract node, using its actual registry identity and the existing `corporateActionPdf` File input. Preserve success/error routing and the reconciliation nodes.
4. Inspect real extraction output before adapting `ValidateCorporateAction`. Deploy/check the run-scoped reference GET on Render, validate the Flow, and run fictional-PDF plus negative-path checks before claiming extraction works.

See [Step 7 setup](IXP_STEP7_SETUP.md). Earlier statements that the model still needed creation are superseded by the verified existing Version 3; the Extract-node integration remains incomplete.
