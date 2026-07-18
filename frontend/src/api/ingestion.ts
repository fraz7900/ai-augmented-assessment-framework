import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { IngestionResult } from './types'

export function useIngestDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, submitter }: { file: File; submitter?: string }) => {
      const form = new FormData()
      form.append('file', file)
      if (submitter) form.append('submitter', submitter)
      return apiClient.postForm<IngestionResult>('/ingest', form)
    },
    onSuccess: () => {
      // A newly ingested document may now be linkable as evidence.
      queryClient.invalidateQueries({ queryKey: ['evidence'] })
    },
  })
}
