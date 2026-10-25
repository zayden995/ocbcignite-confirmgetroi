import { useEffect, useRef, useState } from "react";
import { useTree } from "../../context/TreeContext";
import type { ProofTreeResult } from "../../types";
import { TrustCard } from "./TrustCard";

function Avatar() {
  return (
    <span className="avatar" aria-hidden>
      <svg viewBox="0 0 24 24" width="20" height="20">
        <circle cx="12" cy="9" r="7" fill="#fff" />
        <rect x="10.8" y="13" width="2.4" height="8" rx="1" fill="#fff" />
      </svg>
    </span>
  );
}

export function ChatPanel({
  result, selectedId, onSelectClaim,
}: {
  result: ProofTreeResult | null;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { meta, scenario, scenarioId, selectScenario, role, region, setRole, setRegion, run, loading } = useTree();
  // which scripted question has been "asked" in this conversation
  const [asked, setAsked] = useState<string | null>(null);
  const hasAsked = asked !== null && asked === scenarioId;
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [hasAsked, result, loading]);

  const ask = (id: string) => {
    selectScenario(id);
    setAsked(id);
  };

  return (
    <section className="chat" aria-label="Chat with the OCBC assistant">
      <div className="chat-head">
        <div>
          <strong>OCBC Assistant</strong>
          <span className="chat-sub">Synthetic demo. Answers are scripted.</span>
        </div>
        <div className="profile">
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
        </div>
      </div>

      <div className="thread">
        <div className="msg bot">
          <Avatar />
          <div className="bubble">
            Ask me about SteadyGrowth fixed deposits or transfer channels. Choose one of the sample questions below and I'll answer it, then TREE can check my answer.
          </div>
        </div>

        {hasAsked && scenario && (
          <>
            <div className="msg user">
              <div className="bubble">{scenario.question}</div>
            </div>
            <div className="msg bot">
              <Avatar />
              <div className="bubble">
                <p>{scenario.ai_answer}</p>
                {!result && (
                  <div className="answer-actions">
                    <button className="run" onClick={run} disabled={loading}>
                      {loading ? "Running…" : "Run TREE"}
                    </button>
                    <span className="hint">
                      Checks this answer as a {meta?.roles.find((r) => r.code === role)?.label ?? role} in {meta?.regions.find((r) => r.code === region)?.label ?? region}.
                    </span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {result && hasAsked && <TrustCard result={result} selectedId={selectedId} onSelectClaim={onSelectClaim} />}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <div className="suggest" role="group" aria-label="Sample questions">
          {meta?.scenarios.map((s) => (
            <button key={s.id} className={`suggest-chip${s.id === asked ? " on" : ""}`} onClick={() => ask(s.id)}>
              {s.title}
            </button>
          ))}
        </div>
        <div className="composer-input" aria-disabled>
          <input disabled placeholder="Demo mode: pick a sample question above" aria-label="Message (disabled in demo)" />
          <button disabled className="send" aria-label="Send">➤</button>
        </div>
      </div>
    </section>
  );
}
