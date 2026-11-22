# Judge access

Use [JUDGE_REPRODUCTION_GUIDE.md](JUDGE_REPRODUCTION_GUIDE.md) as the authoritative procedure.

## Public review

The portal and five fictional transfer scenarios are publicly readable at https://transferiq-api.onrender.com/portal. Public browsing does not require the private API key, portal operator code, UiPath credentials, or webhook secrets.

Anonymous isolated demo-run APIs under /api/demo/runs also require no TransferIQ credential. They are allowlisted, quota-bound, TTL-bound, and synthetic. See [API_SURFACES.md](API_SURFACES.md).

## Starting a real workflow

A real portal start requires an owner-supplied operator access code. Approval or rejection occurs only in the real UiPath Action Center Quick Form. Do not share the owner's access code, session secret, webhook configuration, review capability, or UiPath account.

## Reproducing in another tenant

Another tenant must use its own UiPath sign-in, entitlements, folder, HTTP Webhook connection, Agent/Analyze Files availability, and eligible Action Center reviewer. The importer must open Transfer Operations Review in Studio Web and select an assignable single user for that tenant; the saved owner assignment/default reviewer must not be treated as portable.

IXP-in-Flow is unavailable in the Community tenant and is not required. The implemented document route uses the Autonomous Agent's Analyze Files tool with a real file attachment.

All source data and execution records are fictional. A completed workflow does not imply a completed brokerage transfer.
