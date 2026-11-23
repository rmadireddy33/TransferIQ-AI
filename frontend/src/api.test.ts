import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'

const investigationResponse = {
  executionRequestId: 'PEX-0123456789abcdef0123456789abcdef',
  transferId: 'TRF-1002',
  triggerStatus: 'ACCEPTED',
  investigationStatus: 'TRIGGERED',
  reviewStatus: 'NOT_STARTED',
  workflowOutcome: null,
  lastUpdated: '2026-11-22T12:00:00Z',
  startedAt: '2026-11-22T12:00:00Z',
  deadlineAt: '2026-11-22T12:10:00Z',
  verificationStatus: null,
  documentEvidenceStatus: null,
  errorSummary: null,
  auditReference: null,
  runId: null,
  planId: null,
  auditUrl: null,
  investigationSummary: null,
  evidenceReferences: [],
  proposedActions: [],
  unresolvedExceptions: [],
  positionsUnchanged: null,
  transferCompleted: null,
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('portal investigation request security', () => {
  it('sends the session-bound CSRF token and idempotency key', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify(investigationResponse),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ))

    await api.startInvestigation('TRF-1002', 'issued-csrf-token', 'portal-start-idempotency-key')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    const headers = new Headers(init?.headers)
    expect(url).toBe('/api/portal/investigations')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('same-origin')
    expect(headers.get('X-CSRF-Token')).toBe('issued-csrf-token')
    expect(headers.get('Idempotency-Key')).toBe('portal-start-idempotency-key')
  })
})
