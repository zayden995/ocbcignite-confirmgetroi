import type { ProofTreeResult, Status } from "../../types";
import { FailureChips, STATUS_CLASS, StatusBadge } from "../common";

const HEADLINE: Record<Status, { title: string; lead: string }> = {
  Refuted: {
    title: "Don't use this answer yet",
    lead: "TREE found evidence that contradicts at least one claim in it.",
  },
  Unresolved: {
    title: "This answer needs a closer look",
    lead: "TREE could not confirm every claim, or the sources disagree.",
  },
  Verified: {
    title: "This answer holds up",
    lead: "Every claim has strong support and TREE found nothing that challenges it.",
  },
};

export function TrustCard({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { title, lead } = HEADLINE[result.overall.status];
  const disagree = result.baseline.status !== result.overall.status;
  const fixes = result.claims.filter((c) => c.proposed_correction);

  return (
    <section className={`trust ${STATUS_CLASS[result.overall.status]}`} aria-label="TREE trust check">
      <div className="trust-top">
        <StatusBadge status={result.overall.status} big />
        <h3>{title}</h3>
      </div>
      <p className="lead">{lead}</p>

      <div className="compare">
        <div>
          <span className="compare-label">Citation-only check</span>
          <StatusBadge status={result.baseline.status} />
          <span className="compare-note">Checks the cited passage exists and says the same thing. Never looks for exceptions.</span>
        </div>
        <div className="compare-tree">
          <span className="compare-label">TREE</span>
          <StatusBadge status={result.overall.status} />
          <span className="compare-note">Also searches for exceptions, conflicts and out-of-date sources.</span>
        </div>
      </div>
      {disagree && <p className="disagree">The two checks disagree. A citation-only check would have let this through.</p>}

      <h4>Claim by claim</h4>
      <ul className="claim-rows">
        {result.claims.map((c) => (
          <li key={c.id}>
            <button className={`claim-row ${STATUS_CLASS[c.status]}${c.id === selectedId ? " selected" : ""}`} onClick={() => onSelectClaim(c.id)}>
              <span className="dot" aria-hidden />
              <span className="claim-row-text">
                {c.text}
                <FailureChips types={c.failure_types} />
                {c.missing_slots.length > 0 && <span className="claim-row-note">Needs: {c.missing_slots.join(", ")}</span>}
              </span>
              <StatusBadge status={c.status} />
            </button>
          </li>
        ))}
      </ul>

      {fixes.map((c) => (
        <div className="fix" key={c.id}>
          <h4>Suggested correction for claim {c.id.split(".").pop()}</h4>
          <p>{c.proposed_correction!.text}</p>
          <p className="fix-src">
            Based on {c.proposed_correction!.passage_id}
            {c.proposed_correction!.source === "scripted" ? " · scripted in mock mode" : ""}
          </p>
        </div>
      ))}
    </section>
  );
}
