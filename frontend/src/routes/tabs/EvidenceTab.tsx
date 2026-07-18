import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  useEvidenceLinks,
  useLinkEvidence,
  useProposeMappings,
  useReviewEvidence,
} from '../../api/assessments'
import { useFramework } from '../../api/frameworks'
import { findPractice } from '../../lib/practiceLookup'
import EvidenceSourceBadge from '../../components/EvidenceSourceBadge'
import EvidenceReviewControls from '../../components/EvidenceReviewControls'
import ConfidenceMeter from '../../components/ConfidenceMeter'
import type { AssessmentTabContext } from '../AssessmentDetailPage'
import type { EvidenceLink } from '../../api/types'

export default function EvidenceTab() {
  const { assessmentId, assessment } = useOutletContext<AssessmentTabContext>()
  const { data: links, isLoading, isError, error } = useEvidenceLinks(assessmentId)
  const { data: framework } = useFramework(assessment.framework_name)
  const linkEvidence = useLinkEvidence(assessmentId)
  const proposeMappings = useProposeMappings(assessmentId)
  const reviewEvidence = useReviewEvidence(assessmentId)

  const [documentId, setDocumentId] = useState('')
  const [practiceReference, setPracticeReference] = useState('')
  const [chunkId, setChunkId] = useState('')
  const [note, setNote] = useState('')

  const handleLink = (event: React.FormEvent) => {
    event.preventDefault()
    if (!documentId.trim() || !practiceReference.trim()) return
    linkEvidence.mutate(
      {
        document_id: documentId.trim(),
        practice_reference: practiceReference.trim(),
        chunk_id: chunkId.trim() || undefined,
        note: note.trim() || undefined,
        source: 'manual',
      },
      {
        onSuccess: () => {
          setDocumentId('')
          setPracticeReference('')
          setChunkId('')
          setNote('')
        },
      },
    )
  }

  const renderLink = (link: EvidenceLink) => {
    const practice = findPractice(framework, link.practice_reference)
    return (
      <li key={link.id} className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-mono text-xs text-slate-500">{link.practice_reference}</span>{' '}
            <span className="text-sm text-slate-800">{practice?.text ?? '(practice not found in framework)'}</span>
          </div>
          <EvidenceSourceBadge source={link.source} reviewStatus={link.review_status} />
        </div>
        <p className="mt-1 text-xs text-slate-500">
          document {link.document_id}
          {link.chunk_id ? ` · chunk ${link.chunk_id}` : ''}
          {link.note ? ` · "${link.note}"` : ''}
        </p>
        {link.source === 'ai_proposed' && link.confidence != null && (
          <div className="mt-1">
            <ConfidenceMeter value={link.confidence} label="confidence" />
          </div>
        )}
        <div className="mt-2">
          <EvidenceReviewControls
            reviewStatus={link.review_status}
            isSubmitting={reviewEvidence.isPending}
            onAccept={() => reviewEvidence.mutate({ evidenceLinkId: link.id!, body: { decision: 'accepted' } })}
            onReject={() => reviewEvidence.mutate({ evidenceLinkId: link.id!, body: { decision: 'rejected' } })}
            onEdit={(correctedPracticeReference) =>
              reviewEvidence.mutate({
                evidenceLinkId: link.id!,
                body: { decision: 'edited', corrected_practice_reference: correctedPracticeReference },
              })
            }
          />
        </div>
      </li>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Link evidence manually</h2>
          <button
            type="button"
            onClick={() => proposeMappings.mutate()}
            disabled={proposeMappings.isPending || assessment.status === 'finalized'}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {proposeMappings.isPending ? 'Proposing…' : 'Propose AI mappings'}
          </button>
        </div>
        {proposeMappings.isError && (
          <p className="mt-2 text-sm text-red-700">{proposeMappings.error.message}</p>
        )}
        {proposeMappings.isSuccess && (
          <p className="mt-2 text-sm text-emerald-700">
            {proposeMappings.data.length} candidate mapping(s) proposed — pending your review below.
          </p>
        )}

        <form onSubmit={handleLink} className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="document-id">
              Document ID
            </label>
            <input
              id="document-id"
              type="text"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="from Upload"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="practice-reference">
              Practice reference
            </label>
            <input
              id="practice-reference"
              type="text"
              list="practice-ids"
              value={practiceReference}
              onChange={(event) => setPracticeReference(event.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="e.g. ACCESS-1a"
            />
            <datalist id="practice-ids">
              {framework?.domains.flatMap((domain) =>
                domain.objectives.flatMap((objective) =>
                  objective.practices.map((practice) => <option key={practice.id} value={practice.id} />),
                ),
              )}
            </datalist>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="chunk-id">
              Chunk ID (optional)
            </label>
            <input
              id="chunk-id"
              type="text"
              value={chunkId}
              onChange={(event) => setChunkId(event.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="note">
              Note (optional)
            </label>
            <input
              id="note"
              type="text"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={!documentId.trim() || !practiceReference.trim() || linkEvidence.isPending}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {linkEvidence.isPending ? 'Linking…' : 'Link'}
          </button>
        </form>
        {linkEvidence.isError && <p className="mt-2 text-sm text-red-700">{linkEvidence.error.message}</p>}
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Evidence links</h2>
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading…</p>}
        {isError && <p className="mt-2 text-sm text-red-700">{error.message}</p>}
        {links && links.length === 0 && (
          <p className="mt-2 text-sm text-slate-500">No evidence linked yet.</p>
        )}
        {links && links.length > 0 && <ul className="mt-2 space-y-2">{links.map(renderLink)}</ul>}
      </div>
    </div>
  )
}
