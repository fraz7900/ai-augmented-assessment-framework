import type { FrameworkDefinition, Practice } from '../api/types'

// Practice references (e.g. "ACCESS-1a") are shown to users as real practice
// text, never a bare ID — mirrors models/framework.py's Domain.all_practices,
// re-implemented here since the generated schema only carries data shapes,
// not the Pydantic model's convenience methods.
export function findPractice(
  framework: FrameworkDefinition | undefined,
  practiceId: string,
): Practice | undefined {
  if (!framework) return undefined
  for (const domain of framework.domains) {
    for (const objective of domain.objectives) {
      const match = objective.practices.find((practice) => practice.id === practiceId)
      if (match) return match
    }
  }
  return undefined
}
