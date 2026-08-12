import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAssessments, useCreateAssessment } from '../api/assessments'
import { useFrameworkVersions } from '../api/frameworks'
import FrameworkVersionSelect from '../components/FrameworkVersionSelect'
import StatusBadge from '../components/StatusBadge'

// framework_name is free text at the API level (models/assessment.py).
// C2M2, NIST CSF 2.0, NERC CIP, and CIS Controls are fully transcribed
// with real, full requirement text (ADR-0018, ADR-0010, ADR-0022,
// ADR-0025). ISO 27001, SOC 2, and PCI DSS are deliberately statement/
// title-only (ADR-0024, ADR-0026, ADR-0027) — all three are copyrighted,
// all-rights-reserved publications with no reproduction rights granted,
// so Practice.text there is the real official control title / criterion
// statement / Section statement only, never the full descriptive
// requirement, points-of-focus, or Testing Procedures text.
//
// 'NIST CSF' (not 'NIST CSF 2.0') is what new assessments use as of
// ADR-0055: it is the only framework here with two real transcribed
// versions (1.1 and 2.0), and a name with the version baked into it
// cannot hold two. The backend keeps 'NIST CSF 2.0' as a resolvable
// legacy alias so assessments created before that change still work —
// it is deliberately absent from this list, because offering both would
// present the same framework twice.
const KNOWN_FRAMEWORKS = [
  'C2M2',
  'NIST CSF',
  'NERC CIP',
  'ISO 27001',
  'CIS Controls',
  'SOC 2',
  'PCI DSS',
]

export default function AssessmentsListPage() {
  const { data: assessments, isLoading, isError, error } = useAssessments()
  const createAssessment = useCreateAssessment()
  const [name, setName] = useState('')
  const [frameworkName, setFrameworkName] = useState(KNOWN_FRAMEWORKS[0])
  // '' means "whatever the registry considers latest" — sent as an
  // omitted framework_version, which is the API's own default (ADR-0053).
  // Pinning is deliberate: an assessment scored against v2.1 must not
  // silently start meaning something else when v2.2 is added.
  const [frameworkVersion, setFrameworkVersion] = useState('')
  const { data: versions } = useFrameworkVersions(frameworkName)

  // A version chosen for one framework is meaningless for another.
  useEffect(() => setFrameworkVersion(''), [frameworkName])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    createAssessment.mutate(
      {
        name: name.trim(),
        framework_name: frameworkName,
        ...(frameworkVersion ? { framework_version: frameworkVersion } : {}),
      },
      { onSuccess: () => setName('') },
    )
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Assessments</h1>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="assessment-name">
            New assessment name
          </label>
          <input
            id="assessment-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="e.g. 2026 Annual C2M2 Self-Assessment"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="framework-name">
            Framework
          </label>
          <select
            id="framework-name"
            value={frameworkName}
            onChange={(event) => setFrameworkName(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          >
            {KNOWN_FRAMEWORKS.map((framework) => (
              <option key={framework} value={framework}>
                {framework}
              </option>
            ))}
          </select>
        </div>
        <FrameworkVersionSelect
          versions={versions}
          value={frameworkVersion}
          onChange={setFrameworkVersion}
        />
        <button
          type="submit"
          disabled={!name.trim() || createAssessment.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {createAssessment.isPending ? 'Creating…' : 'Create assessment'}
        </button>
      </form>
      {createAssessment.isError && (
        <p className="mt-2 text-sm text-red-700">{createAssessment.error.message}</p>
      )}

      <div className="mt-6 overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
        {isError && <p className="p-4 text-sm text-red-700">{error.message}</p>}
        {assessments && assessments.length === 0 && (
          <p className="p-4 text-sm text-slate-500">No assessments yet — create one above.</p>
        )}
        {assessments && assessments.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Framework</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {assessments.map((assessment) => (
                <tr key={assessment.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link
                      to={`/assessments/${assessment.id}`}
                      className="font-medium text-slate-900 hover:underline"
                    >
                      {assessment.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {assessment.framework_name}
                    {assessment.framework_version && (
                      <span className="ml-1.5 text-xs text-slate-400">
                        {assessment.framework_version}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={assessment.status} />
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {assessment.created_at ? new Date(assessment.created_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
