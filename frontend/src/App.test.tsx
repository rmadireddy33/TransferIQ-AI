import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api'
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
    const investigation = {
      executionRequestId:'PEX-0123456789abcdef0123456789abcdef',transferId:'TRF-1002',triggerStatus:'ACCEPTED',
      investigationStatus:'TRIGGERED' as const,reviewStatus:'NOT_STARTED',workflowOutcome:null,
      lastUpdated:'2026-11-10T00:00:00Z',errorSummary:null,auditReference:null,runId:null,planId:null,
      investigationSummary:null,evidenceReferences:[],proposedActions:[],unresolvedExceptions:[],
      positionsUnchanged:null,transferCompleted:null,
    }
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
})
