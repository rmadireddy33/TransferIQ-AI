import { z } from 'zod'

const positionSchema = z.object({
  securityId: z.string(), classification: z.enum(['MATCHED', 'EXPLAINED', 'UNRESOLVED']),
  sourceQuantity: z.string().nullable(), targetQuantity: z.string().nullable(),
  expectedQuantity: z.string().nullable(), difference: z.string().nullable(),
})
const exceptionSchema = z.object({
  securityId: z.string().nullable(), exceptionType: z.string(), resolutionStatus: z.string(), description: z.string(),
}).passthrough()
export const transferSchema = z.object({
  transferId: z.enum(['TRF-1001', 'TRF-1002', 'TRF-1003', 'TRF-1004', 'TRF-1005']),
  title: z.string(), clientName: z.string(), deliveringFirmName: z.string(), receivingFirmName: z.string(),
  sourceAccountReference: z.string(), destinationAccountReference: z.string(), transferType: z.literal('FULL'),
  transferStatus: z.literal('DRAFT'), lastUpdated: z.string(), evidenceMode: z.literal('PRECOMPUTED_SYNTHETIC_SAMPLE'),
  liveExecution: z.literal(false), reconciliationRunId: z.null(), ruleVersion: z.string(), totalPositions: z.number(),
  directlyMatched: z.number(), evidenceExplained: z.number(), unresolvedCount: z.number(), costBasisIssues: z.number(),
  expectedWorkflowOutcome: z.enum(['CLEAN', 'INVESTIGATION_REQUIRED']), requiresCostBasisReview: z.boolean(),
  quantityReconciliationOnly: z.literal(true), positions: z.array(positionSchema), exceptions: z.array(exceptionSchema),
})
export const catalogSchema = z.object({
  fictionalDemo: z.literal(true), readOnly: z.literal(true), evidenceMode: z.literal('PRECOMPUTED_SYNTHETIC_SAMPLE'),
  notice: z.string(), items: z.array(transferSchema).length(5),
})
const transferDetailSchema = z.object({
  transferId: z.string(), clientId: z.string(), deliveringFirmId: z.string(), receivingFirmId: z.string(),
  sourceAccountId: z.string(), destinationAccountId: z.string(), transferType: z.string(), status: z.string(),
  createdAt: z.string(), updatedAt: z.string(),
}).passthrough()
const pageSchema = z.object({ items: z.array(z.record(z.string(), z.unknown())), total: z.number(), limit: z.number(), offset: z.number() }).passthrough()
const reconciliationSchema = z.object({
  reconciliationRunId: z.string(), transferId: z.string(), status: z.string(), executionStatus: z.string(),
  ruleVersion: z.string(), summary: z.record(z.string(), z.unknown()), positions: z.array(z.record(z.string(), z.unknown())),
  exceptions: z.array(z.record(z.string(), z.unknown())),
}).passthrough()
const referencesSchema = z.object({
  runId: z.string(), transferId: z.string(), securities: z.array(z.record(z.string(), z.unknown())),
  identifierMappings: z.array(z.record(z.string(), z.unknown())), costBasis: z.array(z.record(z.string(), z.unknown())),
}).passthrough()
const planSchema = z.object({
  planId: z.string(), status: z.string(), investigationSummary: z.string(), proposedActions: z.array(z.record(z.string(), z.unknown())),
  evidenceReferences: z.array(z.string()), decision: z.record(z.string(), z.unknown()).nullable().optional(),
}).passthrough()
const verificationSchema = z.object({
  planId: z.string(), planStatus: z.string(), humanReviewOutcome: z.string().nullable(), verificationStatus: z.string(),
  workflowOutcome: z.string(), unresolvedExceptions: z.array(z.record(z.string(), z.unknown())),
  reviewedDispositions: z.array(z.record(z.string(), z.unknown())), positionsUnchanged: z.boolean(), transferCompleted: z.boolean(),
}).passthrough()
const auditSchema = z.object({ planId: z.string(), items: z.array(z.record(z.string(), z.unknown())) }).passthrough()
const portalSessionSchema = z.object({
  enabled: z.boolean(), authorized: z.boolean(), operatorId: z.string().nullable(), csrfToken: z.string().optional(),
})
const investigationSchema = z.object({
  executionRequestId: z.string(), transferId: z.string(), triggerStatus: z.string(), investigationStatus: z.enum([
    'PENDING', 'TRIGGERED', 'INVESTIGATING', 'AWAITING_HUMAN_REVIEW', 'COMPLETED', 'FAILED', 'TIMED_OUT',
  ]), reviewStatus: z.string(), workflowOutcome: z.string().nullable(), lastUpdated: z.string(),
  errorSummary: z.string().nullable(), auditReference: z.string().nullable(), runId: z.string().nullable(),
  planId: z.string().nullable(), investigationSummary: z.string().nullable(), evidenceReferences: z.array(z.string()),
  proposedActions: z.array(z.record(z.string(), z.unknown())), unresolvedExceptions: z.array(z.record(z.string(), z.unknown())),
  positionsUnchanged: z.boolean().nullable(), transferCompleted: z.boolean().nullable(),
})

export type Catalog = z.infer<typeof catalogSchema>
export type DemoTransfer = z.infer<typeof transferSchema>
export type RunBundle = {
  transfer: z.infer<typeof transferDetailSchema>; source: z.infer<typeof pageSchema>; target: z.infer<typeof pageSchema>;
  reconciliation: z.infer<typeof reconciliationSchema> | null; exceptions: z.infer<typeof pageSchema> | null;
  documents: z.infer<typeof pageSchema> | null; references: z.infer<typeof referencesSchema> | null;
}
export type ReviewBundle = { plan: z.infer<typeof planSchema>; verification: z.infer<typeof verificationSchema>; audit: z.infer<typeof auditSchema> }
export type PortalSession = z.infer<typeof portalSessionSchema>
export type InvestigationStatus = z.infer<typeof investigationSchema>

export class ApiError extends Error {
  constructor(public status: number | null, public code: string, message: string, public retryAfter?: string | null) { super(message) }
}

const configured = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''
export const apiBase = configured
export const apiUrl = (path: string) => `${configured}${path}`

async function request<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal,
  init: RequestInit = {}): Promise<T> {
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), 10_000)
  const combined = signal ? AbortSignal.any([signal, timeout.signal]) : timeout.signal
  try {
    const response = await fetch(apiUrl(path), {
      method: 'GET', credentials: 'same-origin', ...init,
      headers: { Accept: 'application/json', ...(init.headers ?? {}) }, signal: combined,
    })
    if (!response.ok) {
      let detail: unknown
      try { detail = await response.json() } catch { detail = null }
      const body = detail as { detail?: { code?: string; message?: string } } | null
      throw new ApiError(response.status, body?.detail?.code ?? `http_${response.status}`,
        body?.detail?.message ?? `TransferIQ returned HTTP ${response.status}.`, response.headers.get('Retry-After'))
    }
    const parsed = schema.safeParse(await response.json())
    if (!parsed.success) throw new ApiError(response.status, 'malformed_response', 'TransferIQ returned an unexpected response shape.')
    return parsed.data
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError(null, 'timeout', 'TransferIQ did not respond within 10 seconds.')
    throw new ApiError(null, 'network_error', 'TransferIQ could not be reached.')
  } finally { clearTimeout(timer) }
}

const optional = async <T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal) => {
  try { return await request(path, schema, signal) } catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error }
}

export const api = {
  catalog: (signal?: AbortSignal) => request('/api/demo/transfers', catalogSchema, signal),
  scenario: (id: string, signal?: AbortSignal) => request(`/api/demo/transfers/${encodeURIComponent(id)}`, transferSchema, signal),
  async run(runId: string, signal?: AbortSignal): Promise<RunBundle> {
    const transfer = await request(`/api/demo/runs/${encodeURIComponent(runId)}/transfer`, transferDetailSchema, signal)
    const root = `/api/demo/runs/${encodeURIComponent(runId)}`
    const [source, target, reconciliation, exceptions, documents, references] = await Promise.all([
      request(`${root}/delivering/accounts/${encodeURIComponent(transfer.sourceAccountId)}/positions?limit=100&offset=0`, pageSchema, signal),
      request(`${root}/receiving/accounts/${encodeURIComponent(transfer.destinationAccountId)}/positions?limit=100&offset=0`, pageSchema, signal),
      optional(`${root}/reconciliation`, reconciliationSchema, signal), optional(`${root}/exceptions?limit=100&offset=0`, pageSchema, signal),
      optional(`${root}/documents?limit=100&offset=0`, pageSchema, signal), optional(`${root}/investigation-references`, referencesSchema, signal),
    ])
    return { transfer, source, target, reconciliation, exceptions, documents, references }
  },
  async review(runId: string, planId: string, signal?: AbortSignal): Promise<ReviewBundle> {
    const root = `/api/demo/runs/${encodeURIComponent(runId)}/resolution-plans/${encodeURIComponent(planId)}`
    const [plan, verification, audit] = await Promise.all([
      request(root, planSchema, signal), request(`${root}/verify`, verificationSchema, signal), request(`${root}/audit`, auditSchema, signal),
    ])
    return { plan, verification, audit }
  },
  documentUrl: (runId: string, documentId: string) => apiUrl(`/api/demo/runs/${encodeURIComponent(runId)}/documents/${encodeURIComponent(documentId)}/download`),
  portalSession: (signal?: AbortSignal) => request('/api/portal/session', portalSessionSchema, signal),
  login: (accessCode: string, signal?: AbortSignal) => request('/api/portal/session', portalSessionSchema, signal, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ accessCode }),
  }),
  startInvestigation: (transferId: string, csrfToken: string, idempotencyKey: string, signal?: AbortSignal) =>
    request('/api/portal/investigations', investigationSchema, signal, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken,
        'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ transferId }),
    }),
  investigation: (executionRequestId: string, signal?: AbortSignal) => request(
    `/api/portal/investigations/${encodeURIComponent(executionRequestId)}`, investigationSchema, signal),
}

export function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return 'An unexpected error occurred.'
  if (error.status === 429) return `Request limit reached.${error.retryAfter ? ` Try again in ${error.retryAfter} seconds.` : ''}`
  return error.message
}
