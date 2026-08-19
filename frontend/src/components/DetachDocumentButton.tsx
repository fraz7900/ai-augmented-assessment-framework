import { Unlink } from 'lucide-react'
import type { DocumentSummary } from '../api/types'

interface Props {
  /** The document currently chosen in the picker, if any. */
  document: DocumentSummary | undefined
  isDisabled?: boolean
  isSubmitting?: boolean
  error: Error | null
  onDetach: (documentId: string) => void
}

/**
 * Remove the chosen document from this assessment (ADR-0062).
 *
 * Acts on whatever the picker has selected, rather than adding a second
 * list of the same documents beside it. Detaching removes only the
 * association: the document itself survives, because it may be attached
 * to other assessments and ingestion is expensive.
 *
 * No confirmation dialog, deliberately. This is fully reversible — the
 * attach control puts it straight back — and the genuinely destructive
 * case cannot happen here: the server refuses (409) while any evidence
 * link still cites the document, since detaching one would leave a
 * citation pointing at a document the assessment no longer claims.
 * Ceremony belongs on the irreversible things, not on this.
 */
export default function DetachDocumentButton({
  document,
  isDisabled = false,
  isSubmitting = false,
  error,
  onDetach,
}: Props) {
  if (isDisabled || !document) return null

  return (
    <div className="mt-1.5">
      <button
        type="button"
        disabled={isSubmitting}
        onClick={() => onDetach(document.id)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:underline disabled:opacity-50"
      >
        <Unlink className="h-3.5 w-3.5" aria-hidden="true" />
        {isSubmitting ? 'Removing…' : `Remove ${document.filename} from this assessment`}
      </button>
      {/*
        The refusal is the interesting case, and the server's message
        names both the count and what to do about it, so it is shown
        verbatim rather than replaced with something vaguer.
      */}
      {error && (
        <p className="mt-1 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
          {error.message}
        </p>
      )}
    </div>
  )
}
