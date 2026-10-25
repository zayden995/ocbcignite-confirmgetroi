import { useEffect, useState } from "react";
import { ClaimDrawer } from "../components/ClaimDrawer";
import { GraphView } from "../components/GraphView";
import { useTree } from "../context/TreeContext";
import { AdminOverview, ConfigTab, CorpusTab, RawJsonTab, TraceTab } from "./admin/tabs";

const TABS = [
  { id: "overview", label: "Run summary", needsResult: true },
  { id: "trace", label: "Pipeline trace", needsResult: true },
  { id: "corpus", label: "Corpus and whitelist", needsResult: false },
  { id: "config", label: "Matrix and settings", needsResult: false },
  { id: "graph", label: "Graph", needsResult: true },
  { id: "json", label: "Raw payload", needsResult: true },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function AdminView() {
  const { meta, scenarioId, selectScenario, role, region, setRole, setRegion, run, loading, result } = useTree();
  const [tab, setTab] = useState<TabId>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => setSelectedId(null), [result]);
  const selected = result?.claims.find((c) => c.id === selectedId) ?? null;
  const current = TABS.find((t) => t.id === tab)!;

  return (
    <main className="admin">
      <div className="admin-head">
        <div>
          <h1>Backend inspector</h1>
          <p>What each stage did for the current run. Read-only; nothing here changes the data.</p>
        </div>
        <div className="admin-controls">
          <label>
            Scenario
            <select value={scenarioId ?? ""} onChange={(e) => selectScenario(e.target.value)}>
              {meta?.scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {meta?.roles.map((r) => (
                <option key={r.code} value={r.code}>{r.label}</option>
              ))}
            </select>
          </label>
          <label>
            Region
            <select value={region} onChange={(e) => setRegion(e.target.value)}>
              {meta?.regions.map((r) => (
                <option key={r.code} value={r.code}>{r.label}</option>
              ))}
            </select>
          </label>
          <button className="run" onClick={run} disabled={loading || !scenarioId}>
            {loading ? "Running…" : "Run TREE"}
          </button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === tab} className={t.id === tab ? "on" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="admin-body" role="tabpanel">
        {current.needsResult && !result ? (
          <p className="empty">Run TREE to fill this tab. Corpus and settings work without a run.</p>
        ) : (
          <>
            {tab === "overview" && result && <AdminOverview result={result} />}
            {tab === "trace" && result && <TraceTab result={result} />}
            {tab === "corpus" && <CorpusTab />}
            {tab === "config" && <ConfigTab />}
            {tab === "graph" && result && <GraphView result={result} selectedId={selectedId} onSelectClaim={setSelectedId} />}
            {tab === "json" && result && <RawJsonTab result={result} />}
          </>
        )}
      </div>

      {result && selected && <ClaimDrawer claim={selected} result={result} onClose={() => setSelectedId(null)} />}
    </main>
  );
}
