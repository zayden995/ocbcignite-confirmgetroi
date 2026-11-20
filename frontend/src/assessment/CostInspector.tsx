import { useState } from "react";
import { useTree } from "../context/TreeContext";
import type { Attempt } from "./types";

function formatCost(amount: number, currency: string) {
  return new Intl.NumberFormat("en", {style: "currency", currency, currencyDisplay: "code",
    minimumFractionDigits: 2, maximumFractionDigits: 9}).format(amount);
}

function costLabel(attempts: Attempt[]) {
  if (!attempts.length) return "No provider call";
  const currency = attempts[0].currency;
  if (attempts.some(a => a.currency !== currency)) return "Unknown · multiple currencies";
  const subtotal = attempts.reduce((n, a) => n + Number(a.estimate ?? 0), 0);
  const formatted = formatCost(subtotal, currency);
  return attempts.some(a => a.estimate === null) ? `Unknown · known subtotal ${formatted}` : formatted;
}

export function CostInspector() {
  const {assessment, activeTurnId} = useTree();
  const [selection, setSelection] = useState("");
  const all = Object.values(assessment.attempts);
  const ids = [...new Set([...Object.keys(assessment.journeys), ...all.map(a => a.turn_id)])];
  const id = selection || (activeTurnId && ids.includes(activeTurnId) ? activeTurnId : ids.at(-1));
  if (!id) return <p className="empty">Check an employee answer to inspect its verification cost.</p>;
  const journey = assessment.journeys[id];
  const attempts = all.filter(a => a.turn_id === id);
  const checks = attempts.filter(a => a.purpose === "verification");
  const revisions = journey?.revisions.map(r => r.request.input_revision) ?? [];
  const first = Math.min(...checks.map(a => a.revision), ...revisions);
  const groups = ids.map(turn => all.filter(a => a.turn_id === turn && a.purpose === "verification"));
  const priced = groups.filter(group => group.length && group.every(a => a.estimate !== null));
  const entries = priced.flat();
  const currencies = new Set(entries.map(a => a.currency));
  const average = currencies.size === 1
    ? formatCost(entries.reduce((sum, a) => sum + Number(a.estimate), 0) / priced.length, entries[0].currency)
    : "Unavailable";
  return <section className="cost-inspector"><h2>Verification cost</h2>
    <label>Employee turn <select value={id} onChange={e => setSelection(e.target.value)}>
      {ids.map(key => <option key={key} value={key}>{assessment.journeys[key]?.draft.question || key} · {key}</option>)}</select></label>
    <p>{journey?.mode === "fixture" ? "Offline fixture · no provider call" : "Live model attempts"} · {id}</p>
    <dl className="cost-grid">{[
      ["Initial verification", costLabel(checks.filter(a => a.revision === first))],
      ["Cumulative verification", costLabel(checks)],
      ["Answer generation", costLabel(attempts.filter(a => a.purpose === "generation"))],
      ["Average per priced live turn", average + " · " + priced.length + " samples"],
    ].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {attempts.length > 0 && <><h3>Provider attempts · {attempts.length}</h3>
      {attempts.map(a => <details key={a.id}><summary>{a.purpose} · revision {a.revision} · {a.model} · {a.success ? "returned" : "failed"} · {a.elapsed_ms} ms</summary>
        <p>{costLabel([a])} · {a.currency} prices dated {a.pricing_date}</p><p>Attempt {a.id}</p>
        {a.usage ? <dl>{Object.entries(a.usage).map(([k,v]) => <div key={k}><dt>{k} tokens</dt><dd>{v ?? "Unknown"}</dd></div>)}</dl> : <p>Usage unavailable</p>}
      </details>)}</>}
  </section>;
}
