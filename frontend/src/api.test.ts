import { describe, expect, it, vi } from 'vitest'
import { api, ApiError, errorMessage } from './api'
import { catalog } from './test/fixtures'

describe('read-only API client', () => {
  it('parses the public catalog and sends only a GET with an Accept header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(catalog()), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.catalog()).resolves.toEqual(catalog())
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/demo/transfers')
    expect(options.method).toBe('GET')
    expect(options.headers).toEqual({ Accept: 'application/json' })
    expect(options.body).toBeUndefined()
  })

  it('fails closed when the backend response shape is incomplete', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 })))
    await expect(api.catalog()).rejects.toMatchObject({ code: 'malformed_response', status: 200 })
  })

  it('reports a bounded 429 response without retrying', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'rate_limited', message: 'Request rate limit exceeded' },
    }), { status: 429, headers: { 'Retry-After': '17' } }))
    vi.stubGlobal('fetch', fetchMock)

    let caught: unknown
    try { await api.catalog() } catch (error) { caught = error }
    expect(caught).toBeInstanceOf(ApiError)
    expect(errorMessage(caught)).toBe('Request limit reached. Try again in 17 seconds.')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('requests operator history with an encoded transfer filter and no write body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [], total: 0, limit: 10, offset: 0,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.investigationHistory(10, 0, undefined, 'TRF-1002')).resolves.toMatchObject({total:0})
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/portal/investigations?limit=10&offset=0&transferId=TRF-1002')
    expect(options.method).toBe('GET')
    expect(options.credentials).toBe('same-origin')
    expect(options.body).toBeUndefined()
  })

  it('encodes identifiers used in document download links', () => {
    expect(api.documentUrl('DEMO-a/b', 'DOC x')).toBe('/api/demo/runs/DEMO-a%2Fb/documents/DOC%20x/download')
  })
})
