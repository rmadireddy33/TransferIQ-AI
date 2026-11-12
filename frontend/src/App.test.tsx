import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api, type InvestigationStatus } from './api'
import { catalog, transfer } from './test/fixtures'

vi.mock('./api', async importOriginal => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      catalog: vi.fn(), scenario: vi.fn(), run: vi.fn(), review: vi.fn(), portalSession: vi.fn(),
      login: vi.fn(), startInvestigation: vi.fn(), investigation: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(api)
const tracked = (overrides: Partial<InvestigationStatus> = {}): InvestigationStatus => ({
  executionRequestId:'PEX-0123456789abcdef0123456789abcdef', transferId:'TRF-1002', triggerStatus:'ACCEPTED',
  investigationStatus:'TRIGGERED', reviewStatus:'NOT_STARTED', workflowOutcome:null,
  startedAt:'2026-11-10T00:00:00Z', lastUpdated:'2026-11-10T00:01:00Z', deadlineAt:'2026-11-10T01:00:00Z',
  verificationStatus:null, errorSummary:null, auditReference:null, auditUrl:null, runId:null, planId:null,
  investigationSummary:null, evidenceReferences:[], proposedActions:[], unresolvedExceptions:[],
  positionsUnchanged:null, transferCompleted:null, ...overrides,
})

describe('Operations portal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mockedApi.catalog.mockResolvedValue(catalog())
    mockedApi.scenario.mockImplementation(async id => transfer(Number(id.slice(-4)), id === 'TRF-1002' ? 'INVESTIGATION_REQUIRED' : 'CLEAN'))
    mockedApi.portalSession.mockResolvedValue({enabled:false,authorized:false,operatorId:null})
  })

  it('renders backend-derived dashboard metrics and filters transfers', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><App /></MemoryRouter>)

    expect(await screen.findByText('Transfer reconciliation at a glance')).toBeInTheDocument()
    expect(screen.getByText('Seeded transfers').nextElementSibling).toHaveTextContent('5')
    expect(screen.getByText('Require investigation').nextElementSibling).toHaveTextContent('2')
    expect(screen.getByRole('link', { name: 'TRF-1002' })).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('Search transfer ID'), '1002')
    expect(screen.getByRole('link', { name: 'TRF-1002' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'TRF-1001' })).not.toBeInTheDocument()
  })

  it('shows the precomputed TRF-1002 shortage without creating a run', async () => {
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/reconciliation']}><App /></MemoryRouter>)

    expect(await screen.findByText('Position reconciliation')).toBeInTheDocument()
    expect(screen.getAllByText('SEC-104').length).toBeGreaterThan(0)
    expect(screen.getByText('-20')).toBeInTheDocument()
    expect(screen.getByText('Unresolved receiving shortage: 20 shares')).toBeInTheDocument()
    expect(mockedApi.run).not.toHaveBeenCalled()
    expect(mockedApi.review).not.toHaveBeenCalled()
  })

  it('keeps the review page read-only when no plan is connected', async () => {
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/review']}><App /></MemoryRouter>)
    expect(await screen.findByText('No review plan connected')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve|reject/i })).not.toBeInTheDocument()
  })

  it('lets an authorized operator start one tracked investigation without approval controls', async () => {
    const user = userEvent.setup()
    const investigation = tracked()
    sessionStorage.setItem('transferiq.csrf','test-csrf')
    mockedApi.portalSession.mockResolvedValueOnce({enabled:true,authorized:true,operatorId:'demo-operator'})
    mockedApi.startInvestigation.mockResolvedValueOnce(investigation)
    mockedApi.investigation.mockResolvedValueOnce(investigation)
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/investigation']}><App /></MemoryRouter>)
    const button=await screen.findByRole('button',{name:'Investigate with AI'})
    await user.click(button)
    await waitFor(()=>expect(mockedApi.startInvestigation).toHaveBeenCalledWith('TRF-1002','test-csrf',expect.stringMatching(/^portal-TRF-1002-/)))
    expect(await screen.findByText('Investigation progress')).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:/approve|reject/i})).not.toBeInTheDocument()
  })

  it('renders an explicit catalog failure state', async () => {
    mockedApi.catalog.mockRejectedValueOnce(new Error('offline'))
    render(<MemoryRouter><App /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument()
  })

  it('shows an approved verified workflow separately from the unresolved transfer', async () => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({
      investigationStatus:'COMPLETED', reviewStatus:'APPROVED', workflowOutcome:'REVIEWED_WITH_OPEN_EXCEPTIONS',
      verificationStatus:'VERIFIED_DEMO_STATE', runId:'DEMO-run', planId:'PLAN-plan', auditReference:'PLAN-plan',
      auditUrl:'/api/demo/runs/DEMO-run/resolution-plans/PLAN-plan/audit',
      investigationSummary:'Verified corporate action; shortage remains open.', positionsUnchanged:true,
      transferCompleted:false, unresolvedExceptions:[{securityId:'SEC-104',difference:'-20',resolutionStatus:'UNRESOLVED'}],
    }))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Workflow completed successfully. The brokerage transfer remains unresolved.')).toBeInTheDocument()
    expect(screen.getByText('VERIFIED_DEMO_STATE')).toBeInTheDocument()
    expect(screen.getByText('-20 · UNRESOLVED')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'View Audit Report'})).toHaveAttribute('href','/api/demo/runs/DEMO-run/resolution-plans/PLAN-plan/audit')
    expect(screen.getByRole('link',{name:'View Transfer Details'})).toHaveAttribute('href','/transfers/TRF-1002/investigation?executionRequestId=PEX-0123456789abcdef0123456789abcdef&runId=DEMO-run&planId=PLAN-plan')
    expect(mockedApi.investigation).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['REVIEW_REJECTED','REJECTED','Review rejected','The human reviewer rejected the plan. No disposition was applied.'],
    ['CLEAN','NOT_REQUIRED','Workflow completed','The persisted workflow result and audit state are available.'],
  ])('renders terminal outcome %s after a direct URL reload', async (outcome,review,stage,message) => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({
      transferId:outcome==='CLEAN'?'TRF-1001':'TRF-1002', investigationStatus:'COMPLETED',
      reviewStatus:review, workflowOutcome:outcome, positionsUnchanged:true, transferCompleted:false,
    }))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText(stage)).toBeInTheDocument()
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(mockedApi.startInvestigation).not.toHaveBeenCalled()
  })

  it('shows the human-review wait state without portal decision controls', async () => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({
      investigationStatus:'AWAITING_HUMAN_REVIEW', reviewStatus:'PENDING', planId:'PLAN-pending',
      investigationSummary:'Plan preview is ready.',
    }))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Awaiting human approval')).toBeInTheDocument()
    expect(screen.getByText(/Complete the real Quick Form/)).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:/approve|reject/i})).not.toBeInTheDocument()
  })

  it('keeps the PEX correlation visible after returning to the transfer', async () => {
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/investigation?executionRequestId=PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Maestro execution available')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'View Maestro progress'})).toHaveAttribute('href','/investigations/PEX-0123456789abcdef0123456789abcdef')
  })

  it.each([
    ['FAILED','Agent execution failed.','Workflow failed'],
    ['TIMED_OUT','Workflow did not reach its configured deadline.','Workflow timed out'],
  ] as const)('renders %s with the sanitized error', async (status,error,stage) => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({investigationStatus:status,errorSummary:error}))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText(stage)).toBeInTheDocument()
    expect(screen.getAllByText(error).length).toBeGreaterThan(0)
  })

  it('stops a bounded active polling window and offers an explicit refresh', async () => {
    vi.useFakeTimers()
    mockedApi.investigation.mockResolvedValue(tracked({investigationStatus:'AWAITING_HUMAN_REVIEW',reviewStatus:'PENDING'}))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    await act(async()=>{await Promise.resolve()})
    await act(async()=>{await vi.advanceTimersByTimeAsync(59*5000)})
    expect(screen.getByText(/Automatic polling has paused after its bounded five-minute window/)).toBeInTheDocument()
    expect(screen.getByRole('button',{name:'Refresh status'})).toBeInTheDocument()
    expect(mockedApi.investigation).toHaveBeenCalledTimes(60)
    vi.useRealTimers()
  })

  it('shows API unavailability and can retry the same persisted tracking URL', async () => {
    mockedApi.investigation.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(tracked())
    const user=userEvent.setup()
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Status unavailable')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'Refresh status'}))
    expect(await screen.findByText('Maestro accepted the request')).toBeInTheDocument()
    expect(mockedApi.startInvestigation).not.toHaveBeenCalled()
  })
})
