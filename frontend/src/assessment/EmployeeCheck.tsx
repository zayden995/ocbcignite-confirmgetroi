import { BranchLayer } from "../components/tree/TreeIllustration";
import { BARK, layoutCanopy, STATUS_PALETTE } from "../components/tree/treeGeometry";
import { useEffect, useMemo, useRef } from "react";
import { useTree, type ChatTurn } from "../context/TreeContext";
import { coverage, decisions, factLabels, tasks, type Fact, type FactKey, type Revision, type Task } from "./types";

function displayFact(f: Fact) {
  if (f.key.endsWith("_cents") && typeof f.value === "number") {
    const digits = String(f.value).padStart(3, "0");
    return digits.slice(0, -2) + "." + digits.slice(-2);
  }
  return String(f.value);
}

function FactEditor({facts, save}: {facts: Fact[]; save: (facts: Fact[]) => void}) {
  function change(key: FactKey, text: string) {
    const rest = facts.filter(f => f.key !== key);
    const value = text.trim();
    if (!value) return save(rest);
    let parsed: string | number = value;
    if (key.endsWith("_cents") && /^\d+(\.\d{1,2})?$/.test(value)) {
      const [whole, fraction = ""] = value.split(".");
      parsed = Number(whole + fraction.padEnd(2, "0"));
    }
    if (key === "tenor_months" && /^\d+$/.test(value)) parsed = Number(value);
    save([...rest, {key, value: parsed, origin: {kind: "form", ref: factLabels[key]}}]);
  }
  return <details className="case-fields"><summary>Employee facts · {facts.length} fields</summary>
    <div className="fact-grid">{(Object.keys(factLabels) as FactKey[]).map(key => {
      const fact = facts.find(f => f.key === key);
      return <label key={key}>{factLabels[key]} <small>{fact?.origin.kind ?? "unknown"}</small>
        <input aria-label={factLabels[key]} defaultValue={fact ? displayFact(fact) : ""} onChange={e => change(key, e.target.value)} />
      </label>;
    })}</div></details>;
}

export function EmployeeCheck({turn}: {turn: ChatTurn}) {
  const {assessment, beginAssessment, setActiveTurnId, selectClaim} = useTree();
  const id = turn.turnId;
  const j = assessment.journeys[id];
  if (!j) return <button className="ghost" disabled={turn.loadingAnswer} onClick={() => {
    beginAssessment(turn); setActiveTurnId(id);
  }}>Check required decisions</button>;
  const d = j.draft;
  const view = j.revisions.find(r => r.result.assessment_id === j.selected);
  const result = view?.result;
  const historic = view && (view.request.input_revision !== d.input_revision || view !== j.revisions.at(-1));
  const edit = (patch: Parameters<typeof assessment.edit>[1]) => assessment.edit(id, patch);
  return <section className="decision-check" aria-label="Decision check">
    <header><strong>Decision check</strong><small>{j.mode === "fixture" ? "Offline fixture" : "Live model"} · {d.employee.role} / {d.employee.region}</small></header>
    <details className="case-fields"><summary>Review question and answer</summary>
      <label>Employee question<textarea aria-label="Employee question" value={d.question} onChange={e => edit({question: e.target.value})}/></label>
      <label>Full answer to check<textarea aria-label="Full answer to check" value={d.answer} onChange={e => edit({answer: e.target.value})}/></label>
      <small>{d.bundle_id} · {d.as_of}</small>
    </details>
    <FactEditor facts={d.facts} save={facts => edit({facts})}/>
    <button className="run" disabled={!!j.pending || !d.question.trim()} onClick={() => {
      setActiveTurnId(id); selectClaim(null); void assessment.run(id);
    }}>{j.pending ? "Checking decisions…" : j.error ? "Retry check" : "Run decision check"}</button>
    {j.error && <p role="alert">Check unavailable · {j.error}</p>}
    {j.revisions.length > 0 && <label>Inspect assessment <select aria-label="Inspect assessment" value={j.selected ?? ""}
      onChange={e => {assessment.select(id, e.target.value); selectClaim(null);}}>
      {!j.selected && <option value="">Edited input · awaiting check</option>}
      {j.revisions.map(r => <option key={r.result.assessment_id} value={r.result.assessment_id}>
        Revision {r.request.input_revision} · {r.result.verdict} · {coverage(r.result)}
      </option>)}</select></label>}
    {view && result && <article className="decision-verdict" aria-live="polite">
      <small>{historic ? "Historical assessment" : "Assessment"} · revision {result.input_revision} · {result.mode}</small>
      <h3>{result.verdict === "ready" ? "Ready" : "Hold"} · {coverage(result)}</h3>
      <strong>{result.task_id ? tasks[result.task_id] : "Task needs review"}</strong>
      <blockquote>{view.request.answer || "Empty answer"}</blockquote>
      <p>{result.next.prompt}</p>
      {result.extras.map(e => <p key={e.span.start}><b>Additional claim · {e.status}</b> “{e.span.quote}” {e.explanation} {e.source_ids.join(", ")}</p>)}
      {!historic && result.next.kind === "clarify_intent" && <div className="decision-actions">
        {([...Object.keys(tasks), "other"] as (Task | "other")[]).map(choice => <button className="ghost" key={choice} onClick={() => {
          edit({confirmation: {choice, input_revision: d.input_revision}}); void assessment.run(id);
        }}>{choice === "other" ? "Something else" : tasks[choice]}</button>)}</div>}
      {!historic && result.repair && <div className="repair">
        <b>Proposed repair</b><blockquote>{result.repair.text}</blockquote><small>{result.repair.source_ids.join(", ")}</small>
        <button className="ghost" onClick={() => edit({answer: result.repair!.text})}>Use proposed answer for recheck</button>
      </div>}
    </article>}
  </section>;
}

export function DecisionTree({revision, open}: {revision: Revision; open: (id: string) => void}) {
  const {result} = revision;
  const layout = useMemo(() => layoutCanopy(result.branches.map(branch => ({id: branch.decision_id, branch}))), [result]);
  return <section className="decision-tree"><div className="tree-panel-head"><h2>Proof Tree</h2>
    <p>{result.task_id ? tasks[result.task_id] : result.next.prompt}</p></div>
    {layout.branches.length > 0 && <svg className="decision-canopy" viewBox={`0 65 1000 ${layout.ground + 90}`} aria-label="Required decisions and policy roots">
      <path d={layout.trunkPath} fill={BARK}/>
      {layout.branches.map(({claim, ...shape}) => {
        const b = claim.branch;
        const color = b.status === "covered" ? STATUS_PALETTE.Verified : b.status === "wrong" ? STATUS_PALETTE.Refuted : STATUS_PALETTE.Unresolved;
        const root = result.roots.find(r => b.source_ids.includes(r.passage_id) && r.state === "governing");
        return <g key={claim.id}><BranchLayer b={{claim, ...shape}} color={color} fill={color.main}/>
          <foreignObject x={shape.center.x - 134} y={shape.center.y - 52} width={268} height={140}>
            <button className={'decision-branch ' + b.status} onClick={() => open(b.decision_id)}>
              <small>Required decision · {b.status.replaceAll("_", " ")}</small>
              <strong>{decisions[b.decision_id]}</strong><span>{b.spans.length ? 'Inspect evidence' : 'No answer text'}</span>
            </button>
          </foreignObject>
          <path d={`M500 ${layout.ground - 10} Q500 ${layout.ground + 32} ${shape.center.x} ${layout.ground + 54}`}
            stroke={BARK} strokeWidth={7} fill="none"/>
          <text x={shape.center.x} y={layout.ground + 85} textAnchor="middle">{root ? root.passage_id + " · v" + root.version : "Policy review"}</text>
        </g>;
      })}
      <rect x="380" y={layout.trunkTop + 42} width="240" height="65" rx="12" fill="white" stroke={BARK}/>
      <text x="500" y={layout.trunkTop + 85} textAnchor="middle">{result.verdict === "ready" ? "Ready" : "Hold"} · {coverage(result)}</text>
    </svg>}
    <small>{result.snapshot_id} · {revision.request.as_of}</small></section>;
}

export function DecisionDrawer({revision, selected, close}: {revision: Revision; selected: string; close: () => void}) {
  const branch = revision.result.branches.find(b => b.decision_id === selected);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prior = document.activeElement;
    button.current?.focus();
    return () => { if (prior instanceof HTMLElement && prior.isConnected) prior.focus(); };
  }, []);
  if (!branch) return null;
  return <aside role="dialog" aria-label={decisions[branch.decision_id]} className="drawer"
    onKeyDown={e => {if (e.key === "Escape") close();}}>
    <div className="drawer-head"><h2>{decisions[branch.decision_id]}</h2><button className="close" ref={button} onClick={close} aria-label="Close">×</button></div>
    <strong>{branch.status.replaceAll("_", " ")}</strong><p>{branch.explanation}</p>
    <h3>Agent answer</h3>{branch.spans.length ? branch.spans.map(s => <blockquote key={s.start}>{s.quote} <small>[{s.start}, {s.end})</small></blockquote>) : <p>No quoted text for this decision.</p>}
    <details className="case-fields"><summary>Employee facts and origins</summary><dl className="meta">{revision.request.facts.filter(f => branch.fact_keys.includes(f.key)).map((f,i) =>
      <div key={i}><dt>{factLabels[f.key]}</dt><dd>{displayFact(f)} · {f.origin.kind} · {f.origin.ref}</dd></div>)}</dl></details>
    <h3>Policy evidence</h3>{revision.result.roots.filter(r => branch.source_ids.includes(r.passage_id)).sort((a, b) => Number(b.state === "governing") - Number(a.state === "governing")).map(r =>
      <section className="pcard" key={r.passage_id}><strong>{r.passage_id} · v{r.version}</strong> <small>{r.state}</small>
        <blockquote>{r.text}</blockquote><p>{r.reason}</p></section>)}
  </aside>;
}
