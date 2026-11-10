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
      catalog: vi.fn(), scenario: vi.fn(), run: vi.fn(), review: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(api)

describe('Operations portal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.catalog.mockResolvedValue(catalog())
    mockedApi.scenario.mockImplementation(async id => transfer(Number(id.slice(-4)), id === 'TRF-1002' ? 'INVESTIGATION_REQUIRED' : 'CLEAN'))
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

  it('renders an explicit catalog failure state', async () => {
    mockedApi.catalog.mockRejectedValueOnce(new Error('offline'))
    render(<MemoryRouter><App /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument()
  })
})
