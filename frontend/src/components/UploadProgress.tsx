import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

interface Props {
  /** Whether an upload is currently in flight. */
  active: boolean
}

/**
 * Feedback while a document is being ingested.
 *
 * This exists because of a real incident, not a hunch. Ingestion is
 * synchronous — POST /ingest parses, chunks and embeds before it
 * responds — and a real 59-page PDF takes about 90 seconds. The UI
 * previously showed the word "Uploading…" and nothing else, so a
 * reviewer had no way to tell a working request from a hung one. They
 * retried twice and ended up with three copies of the same document in
 * the store, which then competed with each other in retrieval.
 *
 * Deliberately NOT a percentage bar. Two things happen after you press
 * Upload: the bytes transfer (fast, and measurable) and the server
 * parses/chunks/embeds (slow, and reports nothing until it finishes).
 * A bar would have to invent progress for the slow phase — the phase
 * that actually makes people give up. An honest elapsed-time counter
 * plus a statement of what is happening is more useful than a bar that
 * lies, and this codebase does not present numbers it cannot support.
 */
export default function UploadProgress({ active }: Props) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!active) {
      setSeconds(0)
      return
    }
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [active])

  if (!active) return null

  const elapsed = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"
    >
      <p className="flex items-center gap-2 font-medium text-slate-900">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Processing document… {elapsed}
      </p>
      <p className="mt-1 text-slate-600">
        The text is being extracted, split into passages, and embedded for search. This happens
        before the response comes back, so a large document takes a while — around a minute and a
        half for a 60-page PDF, and longer for a scanned one that needs reading as an image.
      </p>
      {/*
        The specific warning that would have prevented the duplicate
        uploads. It appears only once the wait is long enough that
        someone would start to doubt the app, rather than nagging from
        second one.
      */}
      {seconds >= 20 && (
        <p className="mt-2 font-medium text-amber-800">
          Still working — please don&apos;t close this tab or press Upload again. Uploading a second
          time creates a duplicate copy of the same document.
        </p>
      )}
    </div>
  )
}
