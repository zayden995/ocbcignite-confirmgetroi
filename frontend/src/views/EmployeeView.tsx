import { useEffect, useState } from "react";
import { ChatPanel } from "../components/chat/ChatPanel";
import { ClaimDrawer } from "../components/ClaimDrawer";
import { SummaryStrip } from "../components/SummaryStrip";
import { TreeIllustration } from "../components/tree/TreeIllustration";
import { useTree } from "../context/TreeContext";

export function EmployeeView() {
  const { result, loading } = useTree();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // a new result invalidates whatever branch was open
  useEffect(() => setSelectedId(null), [result]);
  const selected = result?.claims.find((c) => c.id === selectedId) ?? null;

  return (
    <main className="employee-page">
      <SummaryStrip />
      <div className="employee">
        <ChatPanel result={result} selectedId={selectedId} onSelectClaim={setSelectedId} />

        <section className="tree-panel" aria-label="Proof Tree">
          {result ? (
            <>
              <div className="tree-panel-head">
                <h2>Proof Tree</h2>
                <p>Roots are the source passages, the trunk is the AI's conclusion, and each branch is one claim. Hover for details, click a branch to open it.</p>
              </div>
              <TreeIllustration result={result} selectedId={selectedId} onSelectClaim={setSelectedId} />
            </>
          ) : (
            <div className="welcome">
              <img src="/brand/ocbc-tree-slide.png" alt="OCBC Tree. Get to the root of every answer. Trusted AI for banking decisions." />
              <p>{loading ? "Growing the tree…" : "Ask a question, then press Run TREE to see how the answer holds up."}</p>
            </div>
          )}
        </section>
      </div>

      {result && selected && <ClaimDrawer claim={selected} result={result} onClose={() => setSelectedId(null)} />}
    </main>
  );
}
