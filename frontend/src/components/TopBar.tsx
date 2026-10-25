import { useTree } from "../context/TreeContext";

export function TopBar() {
  const { meta, scenarioId, selectScenario, role, region, setRole, setRegion, run, loading } = useTree();

  return (
    <header className="topbar">
      <div className="brand">
        <h1>OCBC TREE</h1>
        <span className="tagline">Investigate · Challenge · Verify</span>
      </div>
      <div className="badges">
        {meta?.llm_badge && <span className="mock-badge">{meta.llm_badge}</span>}
        {meta && <span className="data-badge">{meta.data_label}</span>}
        {meta && <span className="data-badge">Demo date {meta.demo_date}</span>}
      </div>

      <div className="controls">
        <label>
          Scenario
          <select value={scenarioId ?? ""} onChange={(e) => selectScenario(e.target.value)}>
            {meta?.scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {meta?.roles.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Region
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            {meta?.regions.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <button className="run" onClick={run} disabled={loading || !scenarioId}>
          {loading ? "Running…" : "Run TREE"}
        </button>
      </div>
    </header>
  );
}
