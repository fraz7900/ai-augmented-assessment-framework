interface Props {
  /** Every version the registry knows for the selected framework. */
  versions: string[] | undefined
  /** '' means "let the registry pick the latest". */
  value: string
  onChange: (version: string) => void
}

/**
 * Framework version selection at assessment-creation time (ADR-0055).
 *
 * ADR-0053 added multi-version registry support to the backend --
 * `GET /frameworks/{name}/versions`, `?version=`, and
 * `CreateAssessmentRequest.framework_version` -- and disclosed that no
 * screen reached any of it. This is that gap closed.
 *
 * Three distinct states, deliberately rendered differently:
 *
 * - More than one version: a real choice, so a real <select>, defaulting
 *   to "latest" rather than to a pinned value. Pinning is what stops an
 *   assessment's meaning changing under it when a framework is revised,
 *   but choosing to pin is the user's call, not a default.
 * - Exactly one version (every framework in this project today): a plain
 *   label. A one-option dropdown would imply a decision that does not
 *   exist, while hiding the version entirely would leave the user unable
 *   to see what their assessment is about to be pinned to.
 * - Not loaded, or an unrecognised framework (the endpoint returns [] and
 *   not a 404, so this is a real answer): render nothing rather than an
 *   empty control.
 */
export default function FrameworkVersionSelect({ versions, value, onChange }: Props) {
  if (!versions || versions.length === 0) return null

  if (versions.length === 1) {
    return (
      <p className="pb-1.5 text-sm text-slate-500" data-testid="framework-version-single">
        Version <span className="font-medium text-slate-700">{versions[0]}</span>
      </p>
    )
  }

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700" htmlFor="framework-version">
        Version
      </label>
      <select
        id="framework-version"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
      >
        <option value="">Latest ({versions[versions.length - 1]})</option>
        {versions.map((version) => (
          <option key={version} value={version}>
            {version}
          </option>
        ))}
      </select>
    </div>
  )
}
