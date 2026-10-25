import type { ClaimNodeData, Meta, ProofTreeResult, Status } from "../../types";

/** "Good morning" / "Good afternoon" / "Good evening" (and "Hi" in the small hours), from the viewer's clock. */
export function greeting(now: Date = new Date()): string {
  const h = now.getHours();
  if (h < 5) return "Hi";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/** The demo only knows its sample questions: match typed text to one of them, or to none. */
export function matchQuestion(text: string, scenarios: Meta["scenarios"]): string | null {
  const t = norm(text);
  if (t.length < 12) return null;
  const hit = scenarios.find((s) => {
    const q = norm(s.question);
    return q === t || q.includes(t) || t.includes(q);
  });
  return hit?.id ?? null;
}

/** The claim that decides the verdict: the first Refuted one, else the first Unresolved one. */
export function worstClaim(result: ProofTreeResult): ClaimNodeData | null {
  return (
    result.claims.find((c) => c.status === "Refuted") ?? result.claims.find((c) => c.status === "Unresolved") ?? null
  );
}

export const HEADLINE: Record<Status, string> = {
  Refuted: "Don't use this answer.",
  Unresolved: "Hold off: this can't be confirmed yet.",
  Verified: "This answer checks out.",
};

/** One plain sentence on why the deciding claim failed. Built only from the payload. */
export function plainWhy(result: ProofTreeResult, meta: Meta | null): string {
  const claim = worstClaim(result);
  if (!claim) return "Every claim is backed by a current policy that applies to you, and nothing contradicts it.";

  const root = (id: string) => result.roots.find((r) => r.id === id);
  const driver = claim.evidence.find((e) => e.role === "challenges" && (e.effect === "counts" || e.effect === "conflict"));
  const driverRoot = driver ? root(driver.passage_id) : undefined;
  const bestSupport = claim.evidence.find((e) => e.role === "supports");
  const cited = claim.cited_passage_ids.map(root).filter((r) => r !== undefined);
  const badCited = cited.find((r) => r.state === "filtered_expired" || r.state === "filtered_inapplicable");
  const roleLabel = meta?.roles.find((r) => r.code === result.employee.role)?.label ?? result.employee.role;
  const regionLabel = meta?.regions.find((r) => r.code === result.employee.region)?.label ?? result.employee.region;

  switch (claim.failure_types[0]) {
    case "overlooked_exception":
      return driverRoot
        ? `The answer missed an exception: ${driverRoot.doc_id} (${driverRoot.title}) overrides the rule it relied on.`
        : claim.reason;
    case "conflicting_documents": {
      const other = bestSupport ? root(bestSupport.passage_id) : undefined;
      return driverRoot && other
        ? `${other.doc_id} and ${driverRoot.doc_id} are both current and disagree, and neither outranks the other.`
        : claim.reason;
    }
    case "outdated_or_inapplicable": {
      if (!badCited) return claim.reason;
      const instead = driverRoot ? ` ${driverRoot.doc_id} is the policy that applies to you.` : "";
      return badCited.state === "filtered_expired"
        ? `The source it used (${badCited.doc_id}) is out of date.${instead}`
        : `The policy it used (${badCited.doc_id}) isn't written for a ${roleLabel} in ${regionLabel}.${instead}`;
    }
    case "unsupported_assumption": {
      const failed = claim.conditions.find((c) => c.result === "fail");
      if (failed) return `This case doesn't meet a condition of the policy: ${failed.field.replaceAll("_", " ")} must be ${failed.op} ${String(failed.expected)}.`;
      const labels = result.missing_inputs.map((m) => m.label);
      return `The answer assumes details nobody gave: ${labels.join(", ") || claim.missing_slots.join(", ")}.`;
    }
    default:
      return claim.reason;
  }
}

/** What the employee should do next, in the imperative. */
export function nextStep(result: ProofTreeResult): { label: string; text: string } {
  const claim = worstClaim(result);
  if (!claim) return { label: "You can give this answer to the customer.", text: "" };
  if (claim.status === "Unresolved" && result.missing_inputs.length > 0) {
    return { label: "Before you answer, ask the customer for:", text: result.missing_inputs.map((m) => m.label).join(", ") + "." };
  }
  return {
    label: claim.status === "Refuted" ? "Say this instead:" : "Do this:",
    text: claim.proposed_correction?.text ?? claim.reason,
  };
}
