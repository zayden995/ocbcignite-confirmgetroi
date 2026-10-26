import { useState } from "react";
import { useTree } from "../../context/TreeContext";
import type { ProofTreeResult, Status } from "../../types";
import { FailureChips, STATUS_CLASS, StatusBadge } from "../common";
import { HEADLINE, nextStep, plainWhy } from "./chatUtils";
import { MissingInputForm } from "./MissingInputForm";

const ICON: Record<Status, string> = { Refuted: "✖", Unresolved: "?", Verified: "✔" };

/** The conclusion, as large and plain as it can be: verdict, why, and what to do. Details sit below, closed. */
export function Verdict({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { meta, params, suppliedInputs } = useTree();
  const [reporting, setReporting] = useState(false);
  const status = result.overall.status;
  const why = plainWhy(result, meta);
  const step = nextStep(result);
  const agrees = result.baseline.status === status;

  // fields the form covers: what the employee already reported (so they can change it) plus anything still missing
  const reported = suppliedInputs.filter((d) => params[d.field] !== undefined);
  const formFields = [...reported, ...result.missing_inputs.filter((m) => !reported.some((d) => d.field === m.field))];
  const canReport = status === "Unresolved" && result.missing_inputs.length > 0;

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
        {canReport && !reporting && (
          <button className="ghost-run report-missing" onClick={() => setReporting(true)}>Report missing input</button>
        )}
      </div>

      {reporting && formFields.length > 0 && <MissingInputForm fields={formFields} onClose={() => setReporting(false)} />}

      {reported.length > 0 && !reporting && (
        <p className="reported-note">
          <strong>Based on what you reported: </strong>
          {reported.map((d) => `${d.label} = ${String(params[d.field])}`).join(", ")}.{" "}
          <button className="link-button" onClick={() => setReporting(true)}>Change</button>
        </p>
      )}

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
