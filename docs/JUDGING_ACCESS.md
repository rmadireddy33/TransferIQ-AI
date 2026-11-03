# Judge access

Judges now use real, anonymous, isolated synthetic executions. Follow [the complete credential-free judge setup](ZERO_CREDENTIAL_DEMO.md) for endpoint inventory, Flow import/run steps, safeguards, quotas and independent reproduction. See [actual verification and deployment limitations](ZERO_CREDENTIAL_VERIFICATION.md).

- `/api/demo/runs` creates a bounded run; its transfer, position, reconciliation, exception, PDF and audit operations need no TransferIQ credentials.
- `/api/demo/transfers` list/detail remains a separately labelled **precomputed** sample view. It is not execution evidence.
- All original private business APIs still require `X-API-Key`; arbitrary uploads, transfer creation and private reconciliation are protected. Public corrections, approvals, resets and workflow triggers are absent.
- UiPath sign-in, tenant entitlement and run permissions remain necessary. IXP, Autonomous Agents and human tasks are future integrations with their own tenant requirements.

The earlier read-only-only judging policy and mandatory TransferIQ HTTP connection instructions have been superseded by the requested run-isolated demo model. Do not share the owner's API key or personal UiPath credentials.
