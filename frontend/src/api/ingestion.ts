import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { DocumentDetail, DocumentSummary, IngestionResult } from './types'

// Every ingested document, newest first. Added so the Evidence tab can
// offer a chooser: before this endpoint existed, linking evidence
// required copying a UUID off the Upload screen and pasting it into a
// different tab by hand, because nothing could enumerate what had been
// ingested.
export function useDocuments() {
  return useQuery({
    queryKey: ['documents', 'list'],
    queryFn: () => apiClient.get<DocumentSummary[]>('/documents'),
  })
}

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
      // ...and must appear in the Evidence tab's document chooser
      // immediately. Without this the reviewer uploads a file, switches
      // tab, and cannot find it — the exact dead end the chooser exists
      // to remove.
      queryClient.invalidateQueries({ queryKey: ['documents', 'list'] })
    },
  })
}

// Document-supersession flagging (ADR-0050): GET /documents/{id} has
// existed since ADR-0039 specifically to answer "is this document now
// out of date," but nothing in the frontend called it until this hook.
// Multiple evidence links commonly cite the same document_id -- react-query
// dedupes/caches by queryKey, so N EvidenceLinkCard instances citing the
// same document only trigger one real request, not N.
export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: ['documents', documentId ?? ''],
    queryFn: () => apiClient.get<DocumentDetail>(`/documents/${documentId}`),
    enabled: !!documentId,
  })
}
