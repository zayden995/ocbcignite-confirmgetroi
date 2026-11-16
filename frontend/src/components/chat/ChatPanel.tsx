import { useEffect, useRef } from "react";
import { useTree } from "../../context/TreeContext";
import { Composer } from "./Composer";
import { ProfilePicker } from "./ProfilePicker";
import { Verdict } from "./Verdict";

export function ChatPanel({
  onAsk,
  onNewChat,
}: {
  onAsk: (id: string) => void;
  onNewChat: () => void;
}) {
  const {
    turns,
    activeTurnId,
    setActiveTurnId,
    runForTurn,
    clearChat,
    loading,
    selectedClaimId,
    selectClaim,
  } = useTree();

  const threadRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom when a new turn is added
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTo({
        top: threadRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [turns.length]);

  return (
    <section className="chat" aria-label="Employee assistant chat">
      <div className="chat-head">
        <div>
          <strong>OCBC Internal Assistant</strong>
          <span className="chat-sub">
             Verified by OCBC TREE · {turns.length} {turns.length === 1 ? "turn" : "turns"} in history
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ProfilePicker />
          {turns.length > 0 && (
            <button
              type="button"
              className="ghost small"
              onClick={() => {
                clearChat();
                onNewChat();
              }}
              title="Clear conversation history"
            >
              Clear Chat
            </button>
          )}
        </div>
      </div>

      <div className="thread" ref={threadRef}>
        {turns.length === 0 && (
          <div className="empty">
            Ask a question or pick a starter scenario below to begin.
          </div>
        )}

        {turns.map((turn, index) => {
          const isActive = turn.turnId === activeTurnId;
          const hasThoughts = Boolean(
            turn.scenario.ai_thoughts ||
              (turn.result?.verification_thoughts &&
                turn.result.verification_thoughts.length > 0)
          );

          return (
            <div
              key={turn.turnId}
              onClick={() => setActiveTurnId(turn.turnId)}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                padding: "12px",
                borderRadius: "14px",
                border: isActive
                  ? "2px solid var(--green-deep)"
                  : "1px solid var(--line)",
                background: isActive ? "rgba(46, 125, 50, 0.03)" : "#fff",
                cursor: "pointer",
                transition: "border-color 0.15s, background 0.15s",
              }}
            >
              {/* Turn Header Badge */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "11.5px",
                  color: "var(--muted)",
                  fontWeight: 700,
                }}
              >
                <span>
                  TURN #{index + 1} ·{" "}
                  {turn.scenarioId === "custom"
                    ? "CUSTOM PROMPT"
                    : turn.scenario.title.toUpperCase()}
                </span>
                <span
                  style={{
                    color: isActive ? "var(--green-deep)" : "var(--muted)",
                  }}
                >
                  {isActive ? "● Active on Proof Tree" : "Click to inspect"}
                </span>
              </div>

              {/* 1. User Question Bubble */}
              <div className="msg user">
                <div className="bubble">{turn.scenario.question}</div>
              </div>

              {/* 2. Bot Answer Bubble + Openable Thought Process Tab */}
              <div className="msg bot">
                <div className="avatar" aria-hidden="true">
                  <span style={{ color: "#fff", fontWeight: 800, fontSize: "12px" }}>
                    AI
                  </span>
                </div>
                <div className="bubble" style={{ width: "100%" }}>
                  {/* Openable Thought Process Drawer */}
                  {hasThoughts && (
                    <details
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        marginBottom: "10px",
                        border: "1px solid var(--line)",
                        borderRadius: "10px",
                        background: "#fff",
                        overflow: "hidden",
                      }}
                    >
                      <summary
                        style={{
                          cursor: "pointer",
                          padding: "7px 12px",
                          fontSize: "12.5px",
                          fontWeight: 700,
                          color: "var(--green-deep)",
                          background: "var(--green-wash)",
                          userSelect: "none",
                        }}
                      >
                        ✦ Open AI & TREE Thought Process
                      </summary>
                      <div
                        style={{
                          padding: "10px 12px",
                          fontSize: "12.5px",
                          borderTop: "1px solid var(--line)",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                          maxHeight: "260px",
                          overflowY: "auto",
                        }}
                      >
                        {turn.scenario.ai_thoughts && (
                          <div>
                            <strong
                              style={{
                                display: "block",
                                fontSize: "12px",
                                color: "var(--green-deep)",
                                marginBottom: "4px",
                              }}
                            >
                              1. AI Assistant Generation Reasoning
                            </strong>
                            <pre
                              style={{
                                whiteSpace: "pre-wrap",
                                fontFamily: "var(--mono)",
                                fontSize: "11.5px",
                                background: "var(--mist)",
                                padding: "8px",
                                borderRadius: "6px",
                                margin: 0,
                                color: "var(--ink)",
                              }}
                            >
                              {turn.scenario.ai_thoughts}
                            </pre>
                          </div>
                        )}

                        {turn.result?.verification_thoughts &&
                          turn.result.verification_thoughts.length > 0 && (
                            <div>
                              <strong
                                style={{
                                  display: "block",
                                  fontSize: "12px",
                                  color: "var(--red-deep)",
                                  marginBottom: "4px",
                                }}
                              >
                                2. OCBC TREE Adversarial Verification Trace
                              </strong>
                              <ul
                                style={{
                                  margin: 0,
                                  paddingLeft: "18px",
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "4px",
                                  fontFamily: "var(--mono)",
                                  fontSize: "11.5px",
                                  color: "var(--ink)",
                                }}
                              >
                                {turn.result.verification_thoughts.map((step, i) => (
                                  <li key={i}>{step}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                      </div>
                    </details>
                  )}

                  {/* AI Generated Answer Text */}
                  <p>{turn.scenario.ai_answer}</p>

                  {/* Action Buttons */}
                  <div className="answer-actions">
                    <button
                      type="button"
                      className="run"
                      disabled={
                        loading ||
                        Boolean(turn.loadingAnswer) ||
                        Boolean(turn.loadingVerify)
                      }
                      onClick={(e) => {
                        e.stopPropagation();
                        void runForTurn(turn.turnId);
                      }}
                    >
                      {turn.loadingVerify
                        ? "Running TREE…"
                        : turn.result
                        ? "Re-run TREE"
                        : "Run TREE"}
                    </button>
                    {!turn.result && (
                      <span className="hint">
                        Investigate, challenge &amp; verify this answer
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* 3. Verdict Card (renders when this turn is active and verified) */}
              {turn.result && isActive && (
                <Verdict
                  result={turn.result}
                  selectedId={selectedClaimId}
                  onSelectClaim={selectClaim}
                />
              )}

              {/* Compact Verdict Summary when viewing another turn */}
              {turn.result && !isActive && (
                <div
                  style={{
                    padding: "8px 12px",
                    borderRadius: "10px",
                    background: "var(--mist)",
                    fontSize: "13px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span>
                    Verdict: <strong>{turn.result.overall.status}</strong> —{" "}
                    {turn.result.overall.reason}
                  </span>
                  <span
                    style={{
                      color: "var(--green-deep)",
                      fontWeight: 700,
                      fontSize: "12px",
                    }}
                  >
                    Expand Verdict &amp; Proof Tree →
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Composer onAsk={onAsk} placeholder="Ask a follow-up question…" />
    </section>
  );
}