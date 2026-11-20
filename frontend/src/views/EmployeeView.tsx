import { useEffect } from "react";
import { DecisionDrawer, DecisionTree } from "../assessment/EmployeeCheck";
import { ChatPanel } from "../components/chat/ChatPanel";
import { Landing } from "../components/chat/Landing";
import { ClaimDrawer } from "../components/ClaimDrawer";
import { SummaryStrip } from "../components/SummaryStrip";
import { TreeArt } from "../components/TreeArt";
import { TreeIllustration } from "../components/tree/TreeIllustration";
import { useTree } from "../context/TreeContext";

export function EmployeeView() {
  const { result, loading, selectScenario, assessment, activeTurnId, turns, selectedClaimId: selectedId, selectClaim: setSelectedId } = useTree();
  const journey = assessment.journeys[activeTurnId || ""];
  const revision = journey?.revisions.find(r => r.result.assessment_id === journey.selected);
  useEffect(() => setSelectedId(null), [result, revision, setSelectedId]);
  const selected = result?.claims.find(c => c.id === selectedId);
  const ask = (id: string) => { if (id !== "custom") selectScenario(id); };
  return (
    <main className="employee-page">
      {!turns.length ? (
        <Landing onAsk={ask} />
      ) : (
        <div className="employee">
          <ChatPanel
            onAsk={ask}
          />

          <section className="tree-panel" aria-label="Proof Tree">
            {revision ? <DecisionTree revision={revision} open={setSelectedId}/> : result ? (
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
      {revision && selectedId && <DecisionDrawer revision={revision} selected={selectedId} close={() => setSelectedId(null)}/>}
      {result && selected && <ClaimDrawer claim={selected} result={result} onClose={() => setSelectedId(null)} />}
    </main>
  );
}