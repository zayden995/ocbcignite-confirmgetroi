import { useState } from "react";
import { fetchSummary } from "../api/client";
import type { SummaryResult } from "../types";
import { StatusBadge } from "./common";

export function SummaryStrip() {
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await fetchSummary());
    } catch (e) {
      setSummary(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="summary" aria-label="Baseline versus TREE across the scripted scenarios">
      <div className="summary-head">
        <div>
          <h2>Citation-only check vs TREE</h2>
          <p className="summary-label">Scripted demo set, not a benchmark</p>
        </div>
        {summary && (
          <div className="summary-score" aria-live="polite">
            <span>
              <strong>{summary.baseline_correct} of {summary.total}</strong> citation-only
            </span>
            <span className="tree-score">
              <strong>{summary.tree_correct} of {summary.total}</strong> TREE
            </span>
            <span className="muted small">matched the expected verdict</span>
          </div>
        )}
        <button className="ghost-run" onClick={run} disabled={loading}>
          {loading ? "Running…" : summary ? "Run again" : "Run all 5 scenarios"}
        </button>
      </div>

      {error && <p className="error-inline" role="alert">{error}</p>}

      {summary && (
        <>
          <ul className="summary-grid">
            {summary.scenarios.map((r) => (
              <li key={r.id}>
                <strong>{r.title}</strong>
                <span className="expect">Expected: {r.expected}</span>
                <div className="summary-row">
                  <span>Citation-only</span>
                  <StatusBadge status={r.baseline} />
                  <span className={r.baseline_correct ? "hit" : "miss"}>{r.baseline_correct ? "matches" : "misses"}</span>
                </div>
                <div className="summary-row">
                  <span>TREE</span>
                  <StatusBadge status={r.tree} />
                  <span className={r.tree_correct ? "hit" : "miss"}>{r.tree_correct ? "matches" : "misses"}</span>
                </div>
              </li>
            ))}
          </ul>
          <p className="note">
            These five scenarios were written to contain the failures TREE looks for, and the model outputs are
            scripted{summary.llm_badge ? ` (${summary.llm_badge})` : ""}. This illustrates the pipeline; it is not a measured accuracy.
          </p>
        </>
      )}
    </section>
  );
}
