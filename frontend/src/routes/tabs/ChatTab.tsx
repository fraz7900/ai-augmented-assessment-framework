import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Loader2, Send } from 'lucide-react'
import { useChat } from '../../api/assessments'
import ConfidenceMeter from '../../components/ConfidenceMeter'
import TextProvenanceBadge from '../../components/TextProvenanceBadge'
import type { AssessmentTabContext } from '../AssessmentDetailPage'

// Retrieval-only chat (ADR-0014): every result IS the cited, already
// human-reviewed evidence chunk — nothing is generated, so there is no
// separate "confidence" to model. R-23: similarity is always shown next
// to the result, never hidden behind a pass/fail threshold.
export default function ChatTab() {
  const { assessmentId } = useOutletContext<AssessmentTabContext>()
  const chat = useChat(assessmentId)
  const [question, setQuestion] = useState('')

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!question.trim()) return
    chat.mutate(question.trim())
  }

  return (
    <div className="max-w-2xl space-y-4">
      <p className="text-sm text-slate-600">
        Ask a question grounded only in this assessment&apos;s reviewed evidence. Only
        accepted/edited evidence with a specific cited chunk is answerable.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="e.g. Do we have multi-factor authentication for remote access?"
        />
        <button
          type="submit"
          disabled={!question.trim() || chat.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white enabled:hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {chat.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="h-4 w-4" aria-hidden="true" />
          )}
          {chat.isPending ? 'Asking…' : 'Ask'}
        </button>
      </form>

      {chat.isError && <p className="text-sm text-red-700">{chat.error.message}</p>}

      {chat.isSuccess && (
        <div className="space-y-3">
          {chat.data.results.length === 0 && (
            <p className="text-sm text-slate-500">
              No reviewed evidence was similar enough to this question to cite.
            </p>
          )}
          {chat.data.results.map((result, index) => (
            // ChatResult carries no id (models/chat.py — it's a computed,
            // never-persisted shape, see ADR-0014), and the same chunk can
            // legitimately back more than one EvidenceLink for the same
            // practice (e.g. re-running propose-mappings), so
            // (practice_reference, document_id, chunk_id) is not always
            // unique on its own — index is the defensive tiebreaker.
            <div
              key={`${index}-${result.practice_reference}-${result.document_id}-${result.chunk_id}`}
              className="rounded-lg border border-slate-200 bg-white p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-slate-500">{result.practice_reference}</span>
                <div className="flex items-center gap-2">
                  {/* Next to the quotation it qualifies, not in a footer
                      (ADR-0074). Chat is where this product quotes
                      evidence verbatim, so it is where approximate text
                      does the most damage. */}
                  <TextProvenanceBadge provenance={result.text_provenance} />
                  <ConfidenceMeter value={result.similarity} label="similarity" />
                </div>
              </div>
              <p className="mt-1 text-sm text-slate-800">{result.chunk_text}</p>
              <p className="mt-1 text-xs text-slate-400">
                document {result.document_id} · chunk {result.chunk_id}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
