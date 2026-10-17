import type {
  EvidenceItem,
  EvidencePage,
  EvidenceReference,
} from "../contracts/evidence";
export type EvidenceSubject = Omit<EvidenceItem, "references"> & {
  references: EvidenceReference[];
};
export function evidenceSubjects(page: EvidencePage): EvidenceSubject[] {
  const grouped = new Map<number, EvidenceSubject>();
  for (const item of page.items) {
    const previous = grouped.get(item.sequence);
    const references = [...(previous?.references ?? []), ...item.references];
    grouped.set(item.sequence, {
      ...previous,
      ...item,
      query: item.query ?? previous?.query,
      decision: item.decision ?? previous?.decision,
      observations: item.observations ?? previous?.observations,
      references: references.filter(
        (ref, index) =>
          references.findIndex((other) => other.id === ref.id) === index,
      ),
    });
  }
  return [...grouped.values()].sort((a, b) => a.sequence - b.sequence);
}
