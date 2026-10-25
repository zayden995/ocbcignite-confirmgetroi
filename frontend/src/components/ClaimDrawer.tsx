import { useState } from "react";
import type { ClaimNodeData, ConditionResult, Evidence, ProofTreeResult, RootData } from "../types";
import { FailureChips, StatePill, StatusBadge, fmtValue, shortHash } from "./common";

const EFFECT_TEXT: Record<string, string> = {
  counts: "Counts toward SC",
  counts_support: "Counts toward SE",
  conflict: "Equal-authority conflict: raises a flag, not SC",
  ignored_lower_authority: "Ignored: lower authority than the supporting source",
  not_triggered: "Exception not triggered for this case, so it is excluded from SC",
  needs_input: "Exception might apply but an input is missing, so it is excluded from SC",
};

function Cond({ c }: { c: ConditionResult }) {
  const icon = c.result === "pass" ? "✔" : c.result === "fail" ? "✖" : "?";
  return (
    <li className={`cond ${c.result}`}>
      {icon} {c.field} {c.op} {fmtValue(c.expected)} <span className="muted">(actual: {c.actual == null ? "not provided" : fmtValue(c.actual)})</span>
    </li>
  );
}

function PassageCard({ title, root, evidence, mock }: { title: string; root: RootData | undefined; evidence?: Evidence; mock: boolean }) {
  if (!root) return null;
  return (
    <div className="pcard">
      <h4>{title}</h4>
      <div className="pcard-head">
        <strong>{root.id}</strong> <StatePill state={root.state} label={root.state_label} />
      </div>
      <blockquote>{root.snippet}</blockquote>
      <dl className="meta">
        <dt>Document</dt><dd>{root.doc_id} v{root.version} · {root.title}</dd>
        <dt>Effective</dt><dd>{root.effective_date} to {root.expiry_date}</dd>
        <dt>Authority</dt><dd>level {root.authority}</dd>
        <dt>Source</dt><dd>{root.source.hub}{root.source.path}</dd>
        <dt>SHA-256</dt><dd>{shortHash(root.hash)} {root.hash_ok ? "✔ matches ingestion manifest" : "✖ MISMATCH"}</dd>
        {root.parent_doc_id && (<><dt>Amends</dt><dd>{root.parent_doc_id}</dd></>)}
        {root.supersedes && (<><dt>Supersedes</dt><dd>{root.supersedes}</dd></>)}
        {evidence && (
          <>
            <dt>NLI</dt>
            <dd>{evidence.label} {evidence.score.toFixed(2)}{mock ? " (scripted)" : ""}</dd>
          </>
        )}
        {evidence?.counter_query && (<><dt>Found by</dt><dd className="mono">"{evidence.counter_query.length > 70 ? `${evidence.counter_query.slice(0, 70)}…` : evidence.counter_query}"</dd></>)}
        {evidence?.effect && (
          <>
            <dt>Treatment</dt>
            <dd>{EFFECT_TEXT[evidence.role === "supports" && evidence.effect === "counts" ? "counts_support" : evidence.effect] ?? evidence.effect}</dd>
          </>
        )}
      </dl>
      {evidence && evidence.trigger_conditions.length > 0 && (
        <>
          <div className="small muted">Exception applies only if:</div>
          <ul className="conds">{evidence.trigger_conditions.map((c, i) => <Cond key={i} c={c} />)}</ul>
        </>
      )}
    </div>
  );
}

export function ClaimDrawer({ claim, result, onClose }: { claim: ClaimNodeData; result: ProofTreeResult; onClose: () => void }) {
  const [note, setNote] = useState<string | null>(null);
  const rootOf = (id: string) => result.roots.find((r) => r.id === id);
  const mock = result.llm_badge !== null;
  const supports = claim.evidence.filter((e) => e.role === "supports");
  const challenges = claim.evidence.filter((e) => e.role === "challenges");
  const corr = claim.proposed_correction;

  return (
    <aside className="drawer" role="dialog" aria-label={`Claim ${claim.id}`}>
      <div className="drawer-head">
        <StatusBadge status={claim.status} big />
        <button className="close" onClick={onClose} aria-label="Close">×</button>
      </div>
      <p className="claim-text">{claim.text}</p>
      <p className="small">{claim.reason}</p>

      <div className="se-sc">
        <div><span>SE (support)</span><strong>{claim.se.toFixed(2)}</strong></div>
        <div><span>SC (challenge)</span><strong>{claim.sc.toFixed(2)}</strong></div>
      </div>
      {mock && <p className="small muted">SE/SC are derived from scripted NLI outputs (MOCK LLM), not measured.</p>}

      {claim.failure_types.length > 0 && (
        <>
          <h3>Detected failure</h3>
          <FailureChips types={claim.failure_types} />
        </>
      )}

      {claim.conditions.length > 0 && (
        <>
          <h3>Mandatory conditions</h3>
          <ul className="conds">{claim.conditions.map((c, i) => <Cond key={i} c={c} />)}</ul>
        </>
      )}
      {claim.missing_slots.length > 0 && (
        <p className="small"><strong>Missing input:</strong> {claim.missing_slots.join(", ")}</p>
      )}

      {supports.map((e) => <PassageCard key={e.passage_id} title="Supporting passage" root={rootOf(e.passage_id)} evidence={e} mock={mock} />)}
      {challenges.map((e) => <PassageCard key={e.passage_id} title="Contradicting passage" root={rootOf(e.passage_id)} evidence={e} mock={mock} />)}
      {claim.cited_passage_ids
        .filter((id) => !claim.evidence.some((e) => e.passage_id === id))
        .map((id) => <PassageCard key={id} title="Cited, but gave no usable evidence" root={rootOf(id)} mock={mock} />)}

      {corr && (
        <div className="correction">
          <h3>Proposed correction {corr.source === "scripted" && <span className="muted small">(scripted)</span>}</h3>
          <p>{corr.text}</p>
          <p className="small muted">Justified by {corr.passage_id}</p>
          <blockquote>{rootOf(corr.passage_id)?.snippet}</blockquote>
        </div>
      )}

      <h3>Corrective actions</h3>
      <div className="chips">
        {claim.actions.map((a) => (
          <button key={a} className="chip action" onClick={() => setNote(`Stub action: "${a}" (not wired to anything in this prototype)`)}>
            {a}
          </button>
        ))}
      </div>
      {note && <p className="small muted">{note}</p>}
    </aside>
  );
}
