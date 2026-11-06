# Installed IXP-in-Flow tooling investigation

## Finding

The installed **UiPath CLI 1.205.0** and **@uipath/maestro-builder-sdk 6.66.5** do not expose a documented operation that creates a new IXP model owned by an existing Flow's Extract document node, together with its model-definition resources and ownership/binding metadata. The SDK can author an extraction node and its inline schema **once a real model identity is available**. This is a finding about these installed public interfaces, not a claim that no UiPath internal API could perform the operation.

The exact gap is **provisioning and associating the new in-Flow model**, not writing JSON Schema or calling an existing extractor. No standalone IXP project was created as a substitute. No fake model IDs, folders, predictions or evaluation results were inserted.

## Observed capabilities

| Requested action | Installed interface | Finding / completion |
|---|---|---|
| Create a new model directly inside this Flow | No creation verb in `uip maestro flow`; `dynamicExtract()` requires `model` | Requires visual model builder with current tooling. Not completed. |
| Add an Extract document node | SDK `dynamicExtract()`; node type `uipath.ixp.extract-document-builder` | Supported authoring with existing identity; not proof of model creation. The actual project retains an explicit setup-stop Script until a real model exists. |
| Configure inline field schema and instructions | `dynamicExtract({ schema: ... })`, JSON Schema property descriptions | Eight-field specification and instructions authored in `.flow-sdk/corporate-action-taxonomy.json`; not yet applied to a real model. |
| Create a standalone IXP project | `uip ixp projects create <name> [folder-path]` | Supported, but a different ownership/lifecycle path; deliberately not substituted. |
| Configure taxonomy for an addressable IXP project | `groups add`, `fields add`, `fields update-prompts`, `groups update-prompts`, `projects update-prompt`, `projects import-taxonomy` | Supported for a real project name. No corresponding in-Flow project identity exists yet in this implementation; no cloud taxonomy writes performed. |
| Configure extraction-model settings | `uip ixp projects configure-model <project-name> --model ... --preprocessing ...` | Supported for an existing project. It does not create an in-Flow definition or attach it to a node. |
| Upload sample/training documents | `uip ixp documents upload <project-name> <file>`; optional folder on project creation | Supported for an existing project. The PDF was passed as a real Flow debug attachment, **not uploaded to an IXP training project**. |
| Annotate and inspect predictions | `labellings get-predictions`, `confirm`, `unconfirm`, `mark-missing` | Supported for existing project/document identities. No predictions were confirmed or fabricated. |
| Run model evaluation | Existing-project retraining/evaluation lifecycle plus `projects list-models` and `get-metrics` | Installed project command list has no explicit `evaluate`/`run-evaluation` operation for a new in-Flow model. `get-metrics` reads results; it does not start an evaluation. Use the model builder's Run evaluation for this Flow. |
| Evaluate a Flow | `uip maestro flow eval ... runs` | Supported, but evaluates workflow data points; not equivalent to the IXP model's training/evaluation operation. |
| Bind an existing deployment | `dynamicExtract()` model identity or `ixpExtract()` published-node registry identity | Supported with genuine discovered identities. No newly created model exists to bind here. Preserve designer-created model resources on export/download. |
| File input, HTTP reference lookup, validation, Decisions/error edges | Flow SDK + compile/merge/validate | Implemented in the existing Flow. Original reconciliation nodes retained. |

An in-Flow model might become addressable by some project commands after the designer provisions it. That mapping has not been verified here; do not guess a project slug from the node label or display name.

## Evidence inspected

Installed skill: `C:/Users/ravin/.agents/skills/uipath-maestro-flow/SKILL.md`, particularly `references/document-pipeline.md`, `references/ixp.md` and the brownfield merge procedure.

Installed SDK:

- `package.json`: version 6.66.5.
- `dist/api-index.md`: `dynamicExtract`, `DynamicExtractInputs`, `ixpExtract`, `IxpExtractInputs`.
- `dist/nodes/document/flow/spec.d.ts`: `DynamicExtractInputs` requires `model.modelName` and `model.folderKey`; optional project/folder/version metadata, schema and modelConfig are also supported.
- `dist/nodes/document/flow/factories.d.ts`: documents the extraction-node factories; no model-provisioning method is exposed.

The node-registry search previously returned Extract document, but exact `registry get uipath.ixp.extract-document-builder` returned `NodeNotFound`. Registry discovery alone therefore does not establish that its backing model can be created. The SDK's introductory phrase “INLINE schema” must not be interpreted as model provisioning: its required model identity and the installed `document-pipeline.md` explicitly retain that dependency.

The inspected `projects create` command accepts only a name, optional document folder, description and skip-taxonomy option. It exposes no Flow path, solution ID, node ID, model-resource directory or attachment-to-existing-Flow option. `flow nodes create/add --source` accepts an **existing** dependency UUID; it is not a model creation command.

Reproduce the read-only checks:

```powershell
uip --version
npm list -g @uipath/maestro-builder-sdk --depth=0
uip maestro flow --help --output json
uip maestro flow nodes add --help --output json
uip ixp projects create --help --output json
uip ixp projects --help --output json
uip ixp fields add --help --output json
uip ixp fields update-prompts --help --output json
uip ixp groups --help --output json
uip ixp projects update-prompt --help --output json
uip ixp projects configure-model --help --output json
uip ixp documents upload --help --output json
uip ixp labellings --help --output json
uip ixp projects get-metrics --help --output json
uip maestro flow eval --help --output json
```

## What is ready and what remains

Programmatic preparation is implemented: optional `corporateActionPdf`, eight-field instructions/schema, anonymous run-scoped reference GET, deterministic field/reference comparison, missing-evidence and error paths, evidence result contract, and regression tests. The source was compiled and merged into the existing artifact; product validation returned **Valid with no warnings**. All original HTTP calls remain Manual authentication with no credentials.

Visual completion: create **Document > Extract > Extract document** in the existing Flow; name it CorporateActionExtractor; configure fields, upload/annotate PDFs and run model evaluation; bind the trigger's full File object; retain the prepared success/error edges. Inspect the actual live output before finalizing the strict scalar projection in ValidateCorporateAction. Detailed click-by-click steps and taxonomy are in [IXP_STEP7_SETUP.md](IXP_STEP7_SETUP.md).

Backend completion outside the designer: manually redeploy the new corporate-action reference GET to Render. It was absent from the live OpenAPI at verification time. No deployment was performed.

Verification already executed in this session: **380 backend/contract tests passed**, zero failures; real Maestro TRF-1001 CLEAN; real TRF-1002 without a file INVESTIGATION_REQUIRED plus EVIDENCE_UNAVAILABLE; actual TRF-1002 PDF attachment reached the explicit setup-stop error path. All three runs used successful live HTTP calls and preserved custody/staging positions. **No IXP extraction or model evaluation succeeded or was claimed.** See the setup guide for instance IDs and exact boundaries. This subsequent capability investigation changed documentation only; it did not replace nodes or create cloud resources.

## Current official documentation

[Create a model in the same Flow](https://docs.uipath.com/ixp/automation-cloud/latest/flow-user-guide/consuming-models-via-flow) documents the visual Extract document creation path separately from Published.

The [IXP-in-Flow CLI page](https://docs.uipath.com/ixp/automation-cloud/latest/flow-user-guide/cli) describes the separate `re` CLI and resource/package operations. It does not document a `uip`/builder operation that provisions and attaches this new model inside an existing Flow. No additional CLI, token or undocumented API was introduced.
