import { useState } from 'react'
import { reportUrl, useApproveSanitization, usePreviewSanitization } from '../api/assessments'

// ADR-0032: a sanitized export is only offered once a reviewer has seen the
// diff (matches: what got redacted/pseudonymized and why) and explicitly
// approved it — the approval is hashed against the exact sanitized content,
// so this panel always previews immediately before approving rather than
// letting a stale preview authorize a later export.
export default function SanitizationPanel({ assessmentId }: { assessmentId: string }) {
  const [open, setOpen] = useState(false)
  const [customTermsInput, setCustomTermsInput] = useState('')
  const [approvedBy, setApprovedBy] = useState('')
  const preview = usePreviewSanitization(assessmentId)
  const approve = useApproveSanitization(assessmentId)

  const customTerms = customTermsInput
    .split(',')
    .map((term) => term.trim())
    .filter(Boolean)

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Sanitized export…
      </button>
    )
  }

  return (
    <div className="w-full rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">Sanitized export</h3>
        <button type="button" onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:underline">
          Close
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Redacts emails, phone numbers, IP addresses, and internal hostnames/URLs from the assessment
        name and finding rationales, and pseudonymizes any custom terms you list below (e.g. facility
        or vendor names) as [ORG-TERM-N]. Nothing in the practice text itself is ever altered.
      </p>

      <label className="mt-3 block text-xs font-medium text-slate-700">
        Custom terms to pseudonymize (comma-separated)
      </label>
      <input
        type="text"
        value={customTermsInput}
        onChange={(event) => setCustomTermsInput(event.target.value)}
        placeholder="Northfield Municipal Power & Light, Acme Vendor"
        className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
      />

      <button
        type="button"
        onClick={() => preview.mutate(customTerms)}
        disabled={preview.isPending}
        className="mt-2 rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-800 disabled:opacity-50"
      >
        {preview.isPending ? 'Previewing…' : 'Preview redactions'}
      </button>

      {preview.data && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-2">
          <p className="text-xs font-medium text-slate-700">
            {preview.data.matches.length} redaction{preview.data.matches.length === 1 ? '' : 's'} found
          </p>
          {preview.data.matches.length > 0 && (
            <ul className="mt-1 space-y-1 text-xs text-slate-600">
              {preview.data.matches.map((match, index) => (
                <li key={index}>
                  <span className="font-mono">{match.category}</span> in{' '}
                  <span className="font-mono">{match.field_path}</span>: {match.original_text} →{' '}
                  {match.replacement}
                </li>
              ))}
            </ul>
          )}

          <label className="mt-3 block text-xs font-medium text-slate-700">Approved by</label>
          <input
            type="text"
            value={approvedBy}
            onChange={(event) => setApprovedBy(event.target.value)}
            placeholder="Your name"
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            type="button"
            disabled={!approvedBy.trim() || approve.isPending}
            onClick={() => approve.mutate({ customTerms, approvedBy: approvedBy.trim() })}
            className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {approve.isPending ? 'Approving…' : 'Approve this preview'}
          </button>
        </div>
      )}

      {approve.isSuccess && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-200 pt-3">
          <a
            href={reportUrl(assessmentId, 'pdf', true)}
            className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800 hover:bg-emerald-100"
          >
            Download sanitized PDF
          </a>
          <a
            href={reportUrl(assessmentId, 'xlsx', true)}
            className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800 hover:bg-emerald-100"
          >
            Download sanitized XLSX
          </a>
        </div>
      )}
      {approve.isError && (
        <p className="mt-2 text-xs text-red-700">{approve.error.message}</p>
      )}
    </div>
  )
}
