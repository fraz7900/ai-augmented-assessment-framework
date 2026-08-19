import { useState } from 'react'
import { Building2, Plus } from 'lucide-react'
import { useCreateOrganization } from '../api/organizations'
import { useOrganizationScope } from '../lib/organizationContext'

// Which client the reviewer is working on (ADR-0063), in the app shell
// because it scopes every page below it.
//
// Always visible, even on an instance with exactly one organisation.
// Hiding it there would mean the control appears for the first time on
// the day a second client is added -- which is the day a reviewer is
// most likely to be looking at the wrong one without knowing it. The
// cost of showing it is one line of chrome; the cost of hiding it is
// paid exactly when it matters.
export default function OrganizationSelect() {
  const { organizations, organizationId, setOrganizationId, isLoading } = useOrganizationScope()
  const createOrganization = useCreateOrganization()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')

  if (isLoading) {
    return <span className="text-sm text-slate-400">Loading organizations…</span>
  }

  const handleCreate = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    createOrganization.mutate(trimmed, {
      onSuccess: (organization) => {
        // Switch to what was just created: creating a client and then
        // still looking at the previous one is never what was meant.
        if (organization.id) setOrganizationId(organization.id)
        setName('')
        setAdding(false)
      },
    })
  }

  return (
    <div className="ml-auto flex items-center gap-2">
      <Building2 className="h-4 w-4 text-slate-500" aria-hidden="true" />
      {adding ? (
        <form onSubmit={handleCreate} className="flex items-center gap-2">
          <label className="sr-only" htmlFor="new-organization-name">
            New organization name
          </label>
          <input
            id="new-organization-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Client name"
            className="w-40 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            type="submit"
            disabled={createOrganization.isPending || !name.trim()}
            className="rounded-md bg-slate-900 px-2 py-1 text-sm text-white disabled:opacity-50"
          >
            Add
          </button>
          <button
            type="button"
            onClick={() => {
              setAdding(false)
              setName('')
            }}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Cancel
          </button>
        </form>
      ) : (
        <>
          <label className="sr-only" htmlFor="organization-select">
            Organization
          </label>
          <select
            id="organization-select"
            value={organizationId ?? ''}
            onChange={(event) => setOrganizationId(event.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
          >
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            New
          </button>
        </>
      )}
      {createOrganization.isError ? (
        <span role="alert" className="text-sm text-red-600">
          {createOrganization.error instanceof Error
            ? createOrganization.error.message
            : 'Could not create that organization.'}
        </span>
      ) : null}
    </div>
  )
}
