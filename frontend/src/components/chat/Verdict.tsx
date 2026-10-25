import { useTree } from "../../context/TreeContext";
import type { ProofTreeResult, Status } from "../../types";
import { FailureChips, STATUS_CLASS, StatusBadge } from "../common";
import { HEADLINE, nextStep, plainWhy } from "./chatUtils";

const ICON: Record<Status, string> = { Refuted: "✖", Unresolved: "?", Verified: "✔" };

/** The conclusion, as large and plain as it can be: verdict, why, and what to do. Details sit below, closed. */
export function Verdict({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { meta } = useTree();
  const status = result.overall.status;
  const why = plainWhy(result, meta);
  const step = nextStep(result);
  const agrees = result.baseline.status === status;

  return (
    <section className={`verdict ${STATUS_CLASS[status]}`} aria-label="TREE verdict">
      <div className="verdict-main">
        <span className="verdict-icon" aria-hidden>{ICON[status]}</span>
        <div>
          <StatusBadge status={status} big />
          <h3 className="verdict-headline">{HEADLINE[status]}</h3>
        </div>
      </div>

      <p className="verdict-why"><strong>Why: </strong>{why}</p>
      <div className="verdict-do">
        <strong>{step.label}</strong>
        {step.text && <p>{step.text}</p>}
      </div>

      <p className="verdict-compare">
        {agrees ? (
          <>A citation-only check agrees: <StatusBadge status={result.baseline.status} />.</>
        ) : (
          <>A citation-only check would have said <StatusBadge status={result.baseline.status} />. It can't see this.</>
        )}
      </p>

      <details className="verdict-details">
        <summary>Claim by claim ({result.claims.length})</summary>
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
      </details>
    </section>
  );
}
