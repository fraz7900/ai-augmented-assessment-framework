import { useDocument } from '../api/ingestion'

// Document-supersession flagging (ADR-0050): closes the gap ADR-0039
// disclosed ("a reviewer can query the endpoint but nothing proactively
// flags a superseded document..."). Renders nothing for the common case
// (not superseded, or the document lookup hasn't resolved yet) -- this
// is a warning, not a status this list should be cluttered with by
// default.
export default function SupersededDocumentBadge({ documentId }: { documentId: string }) {
  const { data: document } = useDocument(documentId)
  if (!document?.superseded_by_document_id) return null
  return (
    <span
      className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
      title={`This document has been superseded by document ${document.superseded_by_document_id}`}
    >
      ⚠ document superseded
    </span>
  )
}
