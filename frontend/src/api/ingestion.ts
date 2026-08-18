import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { DocumentDetail, DocumentSummary, IngestionJob } from './types'

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

// NOTE: there is deliberately no hook for the synchronous POST /ingest.
// One existed and every caller has moved to the queued endpoint below,
// so keeping it would leave a second, subtly worse way to upload from
// the browser — the way that fails on exactly the large scanned
// documents this product is for. The endpoint itself remains, and is
// still tested: it is correct for a script that wants to block until
// the work is done, which a browser never does.

/** Whether a job has reached an outcome and will never change again. */
export function isJobFinished(job: IngestionJob | undefined): boolean {
  return job?.status === 'succeeded' || job?.status === 'failed'
}

// How often to ask the server what a running job is doing. Ingestion
// takes tens of seconds to minutes, so a tighter interval would only
// add requests without telling the reviewer anything sooner; a looser
// one would leave a finished 8-second upload looking stuck.
const JOB_POLL_INTERVAL_MS = 2000

// Queue the document instead of waiting for it (POST /ingest/async).
//
// The synchronous POST /ingest still exists and still works, but the
// browser is the one client that cannot use it safely: nginx closes a
// read after 300s, and a large or scanned PDF passes that. The reviewer
// then sees a gateway error for an ingestion that is, in fact, still
// running -- and re-uploads, which is how duplicate copies of one
// document end up competing in retrieval.
//
// Every upload from this page goes through the queue, regardless of
// size. A size threshold would put the two code paths' behaviour on
// opposite sides of a number nobody can see, and the boundary case --
// a 24MB scan that OCRs for six minutes -- is exactly where being wrong
// costs the most.
export function useIngestDocumentAsync() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, submitter }: { file: File; submitter?: string }) => {
      const form = new FormData()
      form.append('file', file)
      if (submitter) form.append('submitter', submitter)
      return apiClient.postForm<IngestionJob>('/ingest/async', form)
    },
    onSuccess: () => {
      // The job list, and ONLY the job list. A 202 means the work was
      // accepted, not done — the document is not linkable yet, so
      // refreshing the document list here would show the reviewer a list
      // that still does not contain the file they just uploaded, which
      // reads as the upload having failed. useIngestionJob invalidates
      // those when the job actually succeeds.
      //
      // The job list does have to move now: the queue may have gone
      // quiet, which stops its polling, and a new upload that does not
      // appear under "Recent uploads" is indistinguishable from one that
      // was never accepted.
      queryClient.invalidateQueries({ queryKey: ['ingestion-jobs', 'list'] })
    },
  })
}

// Poll one job until it reaches an outcome.
//
// Polling stops the moment the job is succeeded or failed -- those are
// terminal in the data model (services/ingestion_job_service.py), so
// asking again could only ever return the same row.
export function useIngestionJob(jobId: string | undefined) {
  const queryClient = useQueryClient()
  const invalidatedFor = useRef<string | null>(null)

  const query = useQuery({
    queryKey: ['ingestion-jobs', jobId ?? ''],
    queryFn: () => apiClient.get<IngestionJob>(`/ingest/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (current) => (isJobFinished(current.state.data) ? false : JOB_POLL_INTERVAL_MS),
  })

  const job = query.data

  useEffect(() => {
    // The synchronous hook could invalidate in onSuccess because its
    // response WAS the outcome. Here the outcome arrives on some later
    // poll, so the same invalidations have to happen on the transition
    // to "succeeded" instead — and exactly once, since polling has
    // already stopped but a refocus can still refetch the finished row.
    if (job?.status !== 'succeeded' || invalidatedFor.current === job.id) return
    invalidatedFor.current = job.id
    queryClient.invalidateQueries({ queryKey: ['evidence'] })
    queryClient.invalidateQueries({ queryKey: ['documents', 'list'] })
    queryClient.invalidateQueries({ queryKey: ['ingestion-jobs', 'list'] })
  }, [job, queryClient])

  return query
}

// Recent ingestion jobs, newest first.
//
// This is what makes a closed tab recoverable. Once the response no
// longer carries the outcome, a reviewer who navigates away mid-ingest
// has no other way to find out whether their document landed — and the
// answer "check whether it appears in the document list" cannot
// distinguish "still running" from "failed".
export function useIngestionJobs(limit = 10) {
  return useQuery({
    queryKey: ['ingestion-jobs', 'list', limit],
    queryFn: () => apiClient.get<IngestionJob[]>(`/ingest/jobs?limit=${limit}`),
    // Keep the list moving while anything on it is still unfinished, so
    // a queued upload visibly becomes a running one without the
    // reviewer reloading the page.
    refetchInterval: (current) =>
      (current.state.data ?? []).every(isJobFinished) ? false : JOB_POLL_INTERVAL_MS,
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
