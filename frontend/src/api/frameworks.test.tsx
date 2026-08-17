import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useFramework } from './frameworks'
import { apiClient } from './client'

// ADR-0058: an assessment pinned to an older framework version must load
// THAT version's definition. The Evidence tab validates practice
// references and renders practice text from it, and since ADR-0055 the
// two real NIST CSF versions share a name but no practice ids at all
// ("ID.AM-1" in 1.1 vs "ID.AM-01" in 2.0) — so loading the wrong one
// shows a reviewer controls that do not exist in the version they are
// assessing against.

function wrapper() {
  // A fresh QueryClient per test: a shared one would let a cache entry
  // from an earlier test satisfy a later one, which is precisely the
  // collision these tests exist to detect.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

function stubFramework(version: string) {
  return { name: 'NIST CSF', version, domains: [] }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useFramework', () => {
  it('requests the pinned version for a NIST CSF 1.1 assessment', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(stubFramework('1.1'))

    const { result } = renderHook(() => useFramework('NIST CSF', '1.1'), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(get).toHaveBeenCalledWith('/frameworks/NIST%20CSF?version=1.1')
    expect(result.current.data?.version).toBe('1.1')
  })

  it('requests the pinned version for a NIST CSF 2.0 assessment', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(stubFramework('2.0'))

    const { result } = renderHook(() => useFramework('NIST CSF', '2.0'), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(get).toHaveBeenCalledWith('/frameworks/NIST%20CSF?version=2.0')
    expect(result.current.data?.version).toBe('2.0')
  })

  it('does not let two versions of one framework collide in the cache', async () => {
    // The actual regression: same name, same QueryClient, different
    // pinned versions. If version were absent from the query key, the
    // second hook would be served the first one's cached 2.0 definition
    // and never issue a request for 1.1.
    const get = vi
      .spyOn(apiClient, 'get')
      .mockImplementation(async (path: string) =>
        path.includes('1.1') ? stubFramework('1.1') : stubFramework('2.0'),
      )
    const sharedWrapper = wrapper()

    const latest = renderHook(() => useFramework('NIST CSF', '2.0'), { wrapper: sharedWrapper })
    await waitFor(() => expect(latest.result.current.isSuccess).toBe(true))

    const pinned = renderHook(() => useFramework('NIST CSF', '1.1'), { wrapper: sharedWrapper })
    await waitFor(() => expect(pinned.result.current.isSuccess).toBe(true))

    expect(latest.result.current.data?.version).toBe('2.0')
    expect(pinned.result.current.data?.version).toBe('1.1')
    expect(get).toHaveBeenCalledWith('/frameworks/NIST%20CSF?version=2.0')
    expect(get).toHaveBeenCalledWith('/frameworks/NIST%20CSF?version=1.1')
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('sends no version for a legacy assessment whose framework_version is null', async () => {
    // Assessments created before ADR-0031 have framework_version = null.
    // They must keep resolving to whatever the registry calls latest,
    // exactly as before — no ?version= on the wire.
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(stubFramework('2.0'))

    const { result } = renderHook(() => useFramework('NIST CSF', null), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(get).toHaveBeenCalledWith('/frameworks/NIST%20CSF')
  })

  it('sends no version when one is simply not supplied', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(stubFramework('2.0'))

    const { result } = renderHook(() => useFramework('C2M2'), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(get).toHaveBeenCalledWith('/frameworks/C2M2')
  })
})
