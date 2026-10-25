import { useEffect, useRef } from "react";
import { useTree } from "../../context/TreeContext";
import type { ProofTreeResult } from "../../types";
import { Composer } from "./Composer";
import { ProfilePicker } from "./ProfilePicker";
import { Verdict } from "./Verdict";

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

const tagOf = (title: string) => title.replace(/^\d+\.\s*/, "").replace(/\s*\(hero\)/, "");

/** The conversation once a question has been asked. */
export function ChatPanel({
  askedId, onAsk, onNewChat, result, selectedId, onSelectClaim,
}: {
  askedId: string;
  onAsk: (id: string) => void;
  onNewChat: () => void;
  result: ProofTreeResult | null;
  selectedId: string | null;
  onSelectClaim: (id: string) => void;
}) {
  const { meta, scenario, run, loading, role, region } = useTree();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [askedId, result, loading]);

  const roleLabel = meta?.roles.find((r) => r.code === role)?.label ?? role;
  const regionLabel = meta?.regions.find((r) => r.code === region)?.label ?? region;

  return (
    <section className="chat" aria-label="Chat with the OCBC assistant">
      <div className="chat-head">
        <div>
          <strong>OCBC Assistant</strong>
          <span className="chat-sub">Synthetic demo. Answers are scripted.</span>
        </div>
        <button className="ghost" onClick={onNewChat}>New chat</button>
      </div>

      <div className="thread">
        {scenario && scenario.id === askedId && (
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
                    <span className="hint">Checks this answer for a {roleLabel} in {regionLabel}.</span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {result && scenario?.id === askedId && <Verdict result={result} selectedId={selectedId} onSelectClaim={onSelectClaim} />}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <ProfilePicker />
        <div className="suggest" role="group" aria-label="Other sample questions">
          {meta?.scenarios.map((s) => (
            <button key={s.id} className={`suggest-chip${s.id === askedId ? " on" : ""}`} onClick={() => onAsk(s.id)}>
              {tagOf(s.title)}
            </button>
          ))}
        </div>
        <Composer onAsk={onAsk} placeholder="Ask another question…" />
      </div>
    </section>
  );
}
