import { useEffect, useState } from "react";
import { ClaimDrawer } from "./components/ClaimDrawer";
import { QAPanel, VerdictCompare } from "./components/Panels";
import { ProofTree } from "./components/ProofTree";
import { TopBar } from "./components/TopBar";
import { useTree } from "./context/TreeContext";

export default function App() {
  const { result, error, loading } = useTree();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // a new result invalidates whatever branch was open
  useEffect(() => setSelectedId(null), [result]);

  const selected = result?.claims.find((c) => c.id === selectedId) ?? null;

  return (
    <div className="app">
      <TopBar />
      <main>
        {error && <div className="error" role="alert">{error}</div>}
        <QAPanel />
        {!result && !loading && !error && (
          <p className="muted empty">Choose a scenario and press <strong>Run TREE</strong>.</p>
        )}
        <VerdictCompare />
        {result && <ProofTree result={result} selectedId={selectedId} onSelectClaim={setSelectedId} />}
      </main>
      {result && selected && <ClaimDrawer claim={selected} result={result} onClose={() => setSelectedId(null)} />}
    </div>
  );
}
