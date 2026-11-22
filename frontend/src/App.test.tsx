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
      login: vi.fn(), startInvestigation: vi.fn(), investigation: vi.fn(), investigationHistory: vi.fn(), plan: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(api)
const tracked = (overrides: Partial<InvestigationStatus> = {}): InvestigationStatus => ({
  executionRequestId:'PEX-0123456789abcdef0123456789abcdef', transferId:'TRF-1002', triggerStatus:'ACCEPTED',
  investigationStatus:'TRIGGERED', reviewStatus:'NOT_STARTED', workflowOutcome:null,
  startedAt:'2026-11-10T00:00:00Z', lastUpdated:'2026-11-10T00:01:00Z', deadlineAt:'2026-11-10T01:00:00Z',
  verificationStatus:null, documentEvidenceStatus:null, errorSummary:null, auditReference:null, auditUrl:null, runId:null, planId:null,
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
    mockedApi.investigation.mockResolvedValue(tracked())
    mockedApi.investigationHistory.mockResolvedValue({items:[],total:0,limit:10,offset:0})
    mockedApi.plan.mockResolvedValue({planId:'PLAN-plan',status:'PREVIEWED',investigationSummary:'Plan summary',
      proposedActions:[],evidenceReferences:[],documentEvidenceStatus:'AGENT_ANALYZE_FILES'})
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
    expect(screen.getByRole('link', { name: 'Investigation History' })).toHaveAttribute('href','/investigations')
  })

  it('protects investigation history behind the existing operator session', async () => {
    mockedApi.portalSession.mockResolvedValueOnce({enabled:true,authorized:false,operatorId:null})
    render(<MemoryRouter initialEntries={['/investigations']}><App /></MemoryRouter>)
    expect(await screen.findByText('Authorized operator access required')).toBeInTheDocument()
    expect(screen.getByLabelText('Authorized demo operator access code')).toBeInTheDocument()
    expect(mockedApi.investigationHistory).not.toHaveBeenCalled()
  })

  it('renders an authorized empty investigation history', async () => {
    mockedApi.portalSession.mockResolvedValueOnce({enabled:true,authorized:true,operatorId:'demo-operator'})
    render(<MemoryRouter initialEntries={['/investigations']}><App /></MemoryRouter>)
    expect(await screen.findByText('No investigations yet')).toBeInTheDocument()
    expect(screen.getByText('No persisted Maestro executions are available for this operator.')).toBeInTheDocument()
    expect(mockedApi.investigationHistory).toHaveBeenCalledWith(10,0,expect.any(AbortSignal))
  })

  it('shows historical results honestly and opens the existing PEX timeline', async () => {
    const user=userEvent.setup()
    const historical=tracked({
      executionRequestId:'PEX-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', investigationStatus:'COMPLETED', reviewStatus:'NOT_REQUIRED',
      workflowOutcome:null, verificationStatus:null, transferCompleted:null,
    })
    const reviewed=tracked({
      executionRequestId:'PEX-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', investigationStatus:'COMPLETED', reviewStatus:'APPROVED',
      workflowOutcome:'REVIEWED_WITH_OPEN_EXCEPTIONS', verificationStatus:'VERIFIED_DEMO_STATE', transferCompleted:false,
      unresolvedExceptions:[{securityId:'SEC-104',difference:'-20',resolutionStatus:'UNRESOLVED'}],
    })
    mockedApi.portalSession.mockResolvedValueOnce({enabled:true,authorized:true,operatorId:'demo-operator'})
    mockedApi.investigationHistory.mockResolvedValueOnce({items:[reviewed,historical],total:2,limit:10,offset:0})
    mockedApi.investigation.mockResolvedValueOnce(reviewed)
    render(<MemoryRouter initialEntries={['/investigations']}><App /></MemoryRouter>)
    expect(await screen.findByText('REVIEWED WITH OPEN EXCEPTIONS')).toBeInTheDocument()
    expect(screen.getByText('OPEN EXCEPTIONS')).toBeInTheDocument()
    expect(screen.getAllByText('Not recorded')).toHaveLength(2)
    const link=screen.getByRole('link',{name:'PEX-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'})
    expect(link).toHaveAttribute('href','/investigations/PEX-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')
    await user.click(link)
    expect(await screen.findByText('Investigation progress')).toBeInTheDocument()
    expect(mockedApi.startInvestigation).not.toHaveBeenCalled()
  })

  it('paginates persisted investigation history without starting workflows', async () => {
    const user=userEvent.setup()
    const firstItems=Array.from({length:10},(_,index)=>tracked({executionRequestId:`PEX-${String(index).padStart(32,'0')}`}))
    const last=tracked({executionRequestId:'PEX-ffffffffffffffffffffffffffffffff'})
    mockedApi.portalSession.mockResolvedValueOnce({enabled:true,authorized:true,operatorId:'demo-operator'})
    mockedApi.investigationHistory
      .mockResolvedValueOnce({items:firstItems,total:11,limit:10,offset:0})
      .mockResolvedValueOnce({items:[last],total:11,limit:10,offset:10})
    render(<MemoryRouter initialEntries={['/investigations']}><App /></MemoryRouter>)
    expect(await screen.findByText('Showing 1–10 of 11')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'Next'}))
    expect(await screen.findByText('Showing 11–11 of 11')).toBeInTheDocument()
    expect(mockedApi.investigationHistory).toHaveBeenLastCalledWith(10,10,expect.any(AbortSignal))
    expect(mockedApi.startInvestigation).not.toHaveBeenCalled()
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

  it('shows the persisted Analyze Files method on the production transfer investigation route', async () => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({
      investigationStatus:'AWAITING_HUMAN_REVIEW', reviewStatus:'PENDING',
      documentEvidenceStatus:'AGENT_ANALYZE_FILES', investigationSummary:'Document fields matched independent API evidence.',
      evidenceReferences:['CA-2026-081'],
    }))
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/investigation?executionRequestId=PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Agent file analysis performed')).toBeInTheDocument()
    expect(screen.getByText('AGENT ANALYZE FILES')).toBeInTheDocument()
    expect(screen.getByText('Document fields matched independent API evidence.')).toBeInTheDocument()
    expect(screen.queryByText(/IXP/i)).not.toBeInTheDocument()
  })

  it.each([
    ['API_ONLY','Structured API evidence used','API ONLY'],
    [null,'Document evidence unavailable','DOCUMENT EVIDENCE UNAVAILABLE'],
  ] as const)('renders document evidence mode %s without claiming file extraction', async (mode, heading, badge) => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({documentEvidenceStatus:mode}))
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText(heading)).toBeInTheDocument()
    expect(screen.getByText(badge)).toBeInTheDocument()
    expect(screen.queryByText(/IXP/i)).not.toBeInTheDocument()
  })

  it('reads the persisted plan method for a pre-migration completed tracking row', async () => {
    mockedApi.investigation.mockResolvedValueOnce(tracked({
      investigationStatus:'COMPLETED', reviewStatus:'APPROVED', workflowOutcome:'REVIEWED_WITH_OPEN_EXCEPTIONS',
      verificationStatus:'VERIFIED_DEMO_STATE', runId:'DEMO-old', planId:'PLAN-old', documentEvidenceStatus:null,
    }))
    mockedApi.plan.mockResolvedValueOnce({planId:'PLAN-old',status:'EXECUTED',investigationSummary:'Historical plan',
      proposedActions:[],evidenceReferences:['CA-2026-081'],documentEvidenceStatus:'AGENT_ANALYZE_FILES'})
    render(<MemoryRouter initialEntries={['/investigations/PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Agent file analysis performed')).toBeInTheDocument()
    expect(mockedApi.plan).toHaveBeenCalledWith('DEMO-old','PLAN-old',expect.any(AbortSignal))
  })

  it.each([
    ['REVIEW_REJECTED','REJECTED','Review rejected','The human reviewer rejected the plan. No disposition was applied.'],
    ['CLEAN','NOT_REQUIRED','Clean outcome recorded','CLEAN reconciliation completed. No human review or resolution-plan audit was required.'],
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
    expect((await screen.findAllByText('Awaiting human review')).length).toBeGreaterThan(0)
    expect(screen.getByText(/Complete the real Quick Form/)).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:/approve|reject/i})).not.toBeInTheDocument()
  })

  it('keeps the PEX correlation visible after returning to the transfer', async () => {
    render(<MemoryRouter initialEntries={['/transfers/TRF-1002/investigation?executionRequestId=PEX-0123456789abcdef0123456789abcdef']}><App /></MemoryRouter>)
    expect(await screen.findByText('Tracked Maestro execution')).toBeInTheDocument()
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
    expect((await screen.findAllByText('Maestro triggered')).length).toBeGreaterThan(0)
    expect(mockedApi.startInvestigation).not.toHaveBeenCalled()
  })
})
