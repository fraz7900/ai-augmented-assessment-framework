import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Identity } from './types'

/**
 * Who the server will attribute this session's decisions to (ADR-0061).
 *
 * The evidence-request forms used to ask "your name" and send it. The
 * server now ignores that in favour of the identity the reverse proxy
 * authenticated, so the field was removed — and removing it without
 * replacing it would leave a reviewer recording decisions under a name
 * they cannot see. This is the replacement: ask the server, and show
 * the answer where the input used to be.
 *
 * Cached for the session. It cannot change without the browser
 * re-authenticating, which reloads the page anyway.
 */
export function useIdentity() {
  return useQuery({
    queryKey: ['identity'],
    queryFn: () => apiClient.get<Identity>('/identity'),
    staleTime: Infinity,
  })
}
