import { useEffect, useState } from "react";
import { ChatPanel } from "../components/chat/ChatPanel";
import { Landing } from "../components/chat/Landing";
import { ClaimDrawer } from "../components/ClaimDrawer";
import { SummaryStrip } from "../components/SummaryStrip";
import { TreeArt } from "../components/TreeArt";
import { TreeIllustration } from "../components/tree/TreeIllustration";
import { useTree } from "../context/TreeContext";

export function EmployeeView() {
  const { result, loading, selectScenario } = useTree();
  // null until a question is asked: that is the "new chat" screen
  const [askedId, setAskedId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // a new result invalidates whatever branch was open
  useEffect(() => setSelectedId(null), [result]);
  const selected = result?.claims.find((c) => c.id === selectedId) ?? null;

  const ask = (id: string) => {
    selectScenario(id);
    setAskedId(id);
  };

  return (
    <main className="employee-page">
      {askedId === null ? (
        <Landing onAsk={ask} />
      ) : (
        <div className="employee">
          <ChatPanel
            askedId={askedId}
            onAsk={ask}
            onNewChat={() => setAskedId(null)}
            result={result}
            selectedId={selectedId}
            onSelectClaim={setSelectedId}
          />

          <section className="tree-panel" aria-label="Proof Tree">
            {result ? (
              <>
                <div className="tree-panel-head">
                  <h2>Proof Tree</h2>
                  <p>Hover a branch or a root for details. Click a branch to open it.</p>
                </div>
                <TreeIllustration result={result} selectedId={selectedId} onSelectClaim={setSelectedId} />
              </>
            ) : (
              <TreeArt caption={loading ? "Growing the tree…" : "Press Run TREE under the answer to see how it holds up."} />
            )}
          </section>
        </div>
      )}

      <SummaryStrip />
      {result && selected && <ClaimDrawer claim={selected} result={result} onClose={() => setSelectedId(null)} />}
    </main>
  );
}
