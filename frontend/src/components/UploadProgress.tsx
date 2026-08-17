import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

/** Which stage of an upload is in flight, or null when none is. */
export type UploadPhase = 'uploading' | 'queued' | 'running'

interface Props {
  phase: UploadPhase | null
}

const phaseHeadings: Record<UploadPhase, string> = {
  uploading: 'Sending document…',
  queued: 'Queued…',
  running: 'Processing document…',
}

const phaseDetail: Record<UploadPhase, string> = {
  uploading:
    'The file is being transferred to the server. This part is quick; the processing that follows is the slow half.',
  // A queued job is genuinely waiting, not working. Saying "processing"
  // here would misreport what the server is doing, and this codebase
  // does not present a number or a state it cannot support.
  queued:
    'Another document is being processed ahead of this one. Documents are handled one at a time so a single upload cannot make the machine unusable for everything else.',
  running:
    'The text is being extracted, split into passages, and embedded for search. A 60-page PDF takes around a minute and a half, and a scanned one that has to be read as an image takes longer.',
}

/**
 * Feedback while a document is being ingested.
 *
 * This exists because of a real incident, not a hunch. A real 59-page
 * PDF takes about 90 seconds to ingest. The UI once showed the word
 * "Uploading…" and nothing else, so a reviewer had no way to tell a
 * working request from a hung one. They retried twice and ended up with
 * three copies of the same document in the store, which then competed
 * with each other in retrieval.
 *
 * Deliberately NOT a percentage bar. Ingestion reports nothing between
 * "started" and "finished", so a bar would have to invent progress for
 * exactly the phase that makes people give up. An honest elapsed-time
 * counter plus a statement of what is actually happening is more useful
 * than a bar that lies.
 *
 * Ingestion is now queued rather than held open on the request
 * (POST /ingest/async), which changes what this panel can honestly
 * promise: the work survives the tab, and "queued" is a real state
 * distinct from "running" that a reviewer will otherwise read as a
 * stall.
 */
export default function UploadProgress({ phase }: Props) {
  const [seconds, setSeconds] = useState(0)
  const active = phase !== null

  useEffect(() => {
    if (!active) {
      setSeconds(0)
      return
    }
    // Keyed on `active`, not on `phase`: the elapsed time a reviewer
    // cares about is since they pressed Upload. Restarting the count at
    // each stage transition would reset it to 0:00 just as the long
    // wait began.
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [active])

  if (phase === null) return null

  const elapsed = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"
    >
      <p className="flex items-center gap-2 font-medium text-slate-900">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        {phaseHeadings[phase]} {elapsed}
      </p>
      <p className="mt-1 text-slate-600">{phaseDetail[phase]}</p>
      {/*
        The specific warning that would have prevented the duplicate
        uploads. It appears only once the wait is long enough that
        someone would start to doubt the app, rather than nagging from
        second one. What it can say has changed: the server now owns the
        work, so leaving is safe — but uploading the same file again
        still queues a second, duplicate copy.
      */}
      {seconds >= 20 && phase !== 'uploading' && (
        <p className="mt-2 text-slate-700">
          Still working. You can leave this page — processing continues on the server, and this
          upload will be listed under <strong>Recent uploads</strong> when you come back.{' '}
          <span className="font-medium text-amber-800">
            Don&apos;t press Upload again: a second upload of the same file creates a duplicate
            copy of the document.
          </span>
        </p>
      )}
    </div>
  )
}
