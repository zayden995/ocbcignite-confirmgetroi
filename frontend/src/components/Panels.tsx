import { useTree } from "../context/TreeContext";
import { StatusBadge } from "./common";

export function QAPanel() {
  const { scenario, result } = useTree();
  if (!scenario) return null;
  return (
    <section className="qa">
      <div className="qa-block">
        <h2>Employee question</h2>
        <p>{scenario.question}</p>
      </div>
      <div className="qa-block">
        <h2>AI answer</h2>
        <p>{scenario.ai_answer}</p>
        {result && (
          <p className="muted small">
            Employee: {result.employee.role} · {result.employee.region} · case parameters{" "}
            {Object.entries(result.employee.params)
              .map(([k, v]) => `${k}=${String(v)}`)
              .join(", ") || "none"}
          </p>
        )}
      </div>
    </section>
  );
}

export function VerdictCompare() {
  const { result } = useTree();
  if (!result) return null;
  const passed = result.baseline.checks.filter((c) => c.entails).length;
  const flagged = result.claims.filter((c) => c.status !== "Verified");
  return (
    <section className="verdicts">
      <div className="verdict-card">
        <h2>Citation-only baseline</h2>
        <StatusBadge status={result.baseline.status} big />
        <p className="small">
          Checked that each cited passage exists and entails its claim ({passed} of{" "}
          {result.baseline.checks.length} citations pass). Never looks for counter-evidence.
        </p>
      </div>
      <div className="vs">vs</div>
      <div className="verdict-card tree">
        <h2>TREE</h2>
        <StatusBadge status={result.overall.status} big />
        <p className="small">
          {flagged.length
            ? `${flagged.length} of ${result.claims.length} claims not verified after challenging them.`
            : "All claims survived the challenge stage."}
        </p>
      </div>
    </section>
  );
}
