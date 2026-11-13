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
