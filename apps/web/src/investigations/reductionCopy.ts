import type { ReductionSummary } from "../contracts/evidence";

export const reductionReasons: Record<string, string> = {
  verified: "Smaller case verified. The same difference remains.",
  invalid_candidate: "This change isn't a valid case.",
  unsupported_shape: "This change isn't supported.",
  not_smaller: "The case is not smaller.",
  duplicate: "This case has already been considered.",
  difference_eliminated: "The difference disappeared.",
  signature_changed: "A different difference was observed.",
  execution_failure:
    "We couldn't verify this change. The last verified case is preserved.",
  integrity_failure: "Saved evidence could not be verified.",
  supported_passes_exhausted:
    "No smaller case found with the supported reductions.",
  candidate_limit:
    "Reduction stopped at its comparison limit. The last verified case is preserved.",
  consideration_limit:
    "Reduction stopped at its proposal limit. The last verified case is preserved.",
  time_limit:
    "Reduction stopped at its time limit. The last verified case is preserved.",
  storage_limit:
    "Reduction stopped at its storage limit. The last verified case is preserved.",
  event_limit:
    "Reduction stopped at its history limit. The last verified case is preserved.",
  unstable_source:
    "The difference changed when checked again. Reduction was not started.",
  cancelled: "Investigation cancelled. Collected evidence is preserved.",
  verification_failed:
    "We couldn't verify this change. The last verified case is preserved.",
};

export function reductionAction(summary: ReductionSummary) {
  if (summary.stopReason) return reductionReasons[summary.stopReason];
  if (summary.state === "checking") return "Checking the difference again.";
  if (summary.state === "verifying") return "Verifying a smaller case.";
  return "Looking for a smaller case.";
}
