# Investigation notes

- Anchor: Maestro Flow debug instance `a99ae4d3-242d-43fc-bf92-eead087dbbc3` supplied by the user.
- Folder: `ff1e40d3-3531-41ec-bb0c-270f86f7043d` (Studio Web Debug).
- Instance: created 2026-11-13T02:36:28.9826228Z, started 02:36:31.8937501Z, completed 02:39:20.7932539Z, no incidents.
- Agent job: `1d828568-6df6-4222-afc4-5be0cd365401`, Successful. Logs contain real `Analyze_Files` state updates and successful retrieval of the PDF attachment. Signed attachment URLs were not copied into documentation.
- Proven correction: the Flow node retained direct `$vars` prompt expressions and supplied a real job-attachment UUID. Earlier literal `input.*` attachment placeholders no longer reached Analyze Files.
- Agent document evidence: `CORPORATE_ACTION_NOTICE`; SEC-103; STOCK_SPLIT 2:1; effective 2026-08-10; notice 2026-08-15; evidence reference CA-2026-081; extraction method AGENT_ANALYZE_FILES.
- Deterministic validation: VERIFIED against the corporate-action API. SEC-103 explained; SEC-104 unresolved at expected/source 120, receiving 100, difference -20.
- Backend correlation: run `DEMO-95cfd248680a41f39b633ac7dddd2c93`, reconciliation `REC-96fd50e7-f950-4eb5-a387-17bd76e386b3`, plan `PLAN-8202710c-cef1-4d1b-8409-512d37736467`.
- Human review: Quick Form task `100313544`, Approve. Plan status EXECUTED.
- Final: REVIEWED_WITH_OPEN_EXCEPTIONS / VERIFIED_DEMO_STATE; positionsUnchanged=true; transferCompleted=false; correctionsApplied=0.
- Audit GET HTTP 200 with PLAN_PREVIEWED, DEMO_REVIEW_RECORDED, and DEMO_DISPOSITION_EXECUTED.
- Trace export command hung and was interrupted; no successful trace-export claim is made. Existing read-only instance, element, variable, job, and log evidence was sufficient.
- Phase B: automated retrieval implemented and validated locally, not deployed or live-tested.

## Phase B portal acceptance — PEX-13e348fd5f1a4e87884e4abfa866d21b

- Exact PEX correlated in runtime variables to deployed Flow instance `7864b5c0-f881-4bd1-91fa-197a0f800733`, package 1.1.0, source `IntegrationTrigger`, folder `DemoFolder/TransferIQ-AI`.
- Instance ran 2026-11-13T04:05:24.1724937Z through 04:05:55.9200407Z. Top-level state is Completed because the controlled `AgentFailed` branch completed; the `TransferInvestigationAgent` element itself is Failed.
- API Workflow `TransferIQ_Reconciliation.api.TransferIQ_Document_Retrieval@1.1.0` completed. Every retrieval task completed: list metadata, select notice, read content, validate response, convert base64 to file, and return attachment.
- Retrieval result: AVAILABLE; document `DOC-be94ea38-bd83-4d14-b03b-af83c8322348`; type `CORPORATE_ACTION_NOTICE`; PDF attachment ID `b615785e-e45a-45c3-a2dc-08df411df333`; MIME `application/pdf`; checksum `a4ea1506d5a31d1f591b916ffe9144c0ca97910ab9fa67bafe742fee7f985b64`.
- Agent job `b4d0b6da-e767-4d57-a9d8-5c913c0e82ef`, agent version 1.1.0, failed before Analyze Files/LLM execution with `AGENT_STARTUP.INPUT_VALIDATION_ERROR`.
- Exact discriminator: runtime input `agentDocument.Metadata.Size` is integer `2627`; deployed agent input schema requires every Metadata value to be a string. Error: `Input should be a valid string [type=string_type, input_value=2627, input_type=int]`.
- This matches the Agents `input-schema-validation-failure.md` playbook, Variant B: the caller passed a wrong input type. It is not an unavailable document, corrupt PDF, API failure, missing resource, or financial-engine failure.
- Reconciliation completed before the agent: demo run `DEMO-3a4cfbeda09e448c86650f5e094b3b83`, reconciliation `REC-284702ca-6e92-4d63-979f-ca379997635a`; SEC-103 was API-explained by `CA-2026-081`; SEC-104 remained unresolved, expected 120 versus staged 100, difference -20.
- No plan preview, Quick Form, decision, disposition execution, or final audit ran. `correctionsApplied=0`, `transferCompleted=false`; custody/staging positions were unchanged.
- Confirmed minimal repair: loosen the agent JobAttachment `Metadata` schema from `additionalProperties: {type: string}` to an untyped object, matching the API Workflow's JobAttachment output schema and the real Base64-to-File payload. This affects attachment transport only.
- Verification checklist: cause named = Variant B caller wrong type; runtime evidence = correlated agentRun span and Flow variables; sibling causes rejected by successful API Workflow tasks and valid attachment identity/MIME; resolution = correct payload/schema type; fix scope = JobAttachment Metadata schema only.
