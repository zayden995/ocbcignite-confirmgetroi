import { useState, type FormEvent } from "react";
import { useTree } from "../../context/TreeContext";
import type { MissingInput } from "../../types";

/** Parse what was typed into the value the backend expects; null means "not valid yet". */
function parseValue(def: MissingInput, raw: string): unknown | null {
  const text = raw.trim();
  if (text === "") return null;
  if (def.type === "number") {
    const n = Number(text);
    return Number.isFinite(n) && n >= 0 ? n : null;
  }
  if (def.type === "select") return def.options.includes(text) ? text : null;
  return text;
}

/** Lets the employee report what the customer told them, then re-runs TREE with it. */
export function MissingInputForm({ fields, onClose }: { fields: MissingInput[]; onClose: () => void }) {
  const { params, rerun, loading } = useTree();
  const [raw, setRaw] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.field, params[f.field] === undefined ? "" : String(params[f.field])])),
  );
  const [error, setError] = useState<string | null>(null);

  const parsed = fields.map((f) => [f, parseValue(f, raw[f.field] ?? "")] as const);
  const ready = parsed.every(([, v]) => v !== null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready || loading) return;
    setError(null);
    const message = await rerun(Object.fromEntries(parsed.map(([f, v]) => [f.field, v])), fields);
    if (message) setError(message);
    else onClose();
  };

  return (
    <form className="missing-form" onSubmit={submit} aria-label="Report missing input">
      <p className="missing-form-intro">Enter what the customer told you. TREE will check the answer again with it.</p>
      {fields.map((f) => {
        const id = `missing-${f.field}`;
        return (
          <div className="missing-field" key={f.field}>
            <label htmlFor={id}>{f.label}</label>
            {f.type === "select" ? (
              <select id={id} value={raw[f.field]} onChange={(e) => setRaw((r) => ({ ...r, [f.field]: e.target.value }))}>
                <option value="">Choose…</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            ) : (
              <input
                id={id}
                type={f.type === "number" ? "number" : "text"}
                min={f.type === "number" ? 0 : undefined}
                inputMode={f.type === "number" ? "decimal" : undefined}
                value={raw[f.field]}
                onChange={(e) => setRaw((r) => ({ ...r, [f.field]: e.target.value }))}
              />
            )}
          </div>
        );
      })}
      {error && <p className="missing-form-error" role="alert">Could not re-run TREE: {error}</p>}
      <div className="answer-actions">
        <button type="submit" className="run" disabled={!ready || loading}>{loading ? "Running…" : "Re-run TREE"}</button>
        <button type="button" className="ghost" onClick={onClose} disabled={loading}>Cancel</button>
      </div>
    </form>
  );
}
