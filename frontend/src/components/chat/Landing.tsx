import { useMemo } from "react";
import { useTree } from "../../context/TreeContext";
import { TreeArt } from "../TreeArt";
import { Composer } from "./Composer";
import { ProfilePicker } from "./ProfilePicker";
import { greeting } from "./chatUtils";

const tagOf = (title: string) => title.replace(/^\d+\.\s*/, "").replace(/\s*\(hero\)/, "");

/** First screen: an empty chat, like opening a new conversation. */
export function Landing({ onAsk }: { onAsk: (id: string) => void }) {
  const { meta } = useTree();
  const hello = useMemo(() => greeting(), []);

  return (
    <section className="landing" aria-label="New chat">
      <div className="landing-copy">
        <h1>{hello}, how may I help you?</h1>
        <p className="landing-sub">Ask a question. I'll answer, and TREE will check whether my answer is safe to use.</p>

        <Composer onAsk={onAsk} placeholder="Ask about deposits or transfers…" autoFocus />
        <ProfilePicker withNote />

        <div className="starters" role="group" aria-label="Sample questions">
          <h2>Or try one of these</h2>
          <div className="starter-grid">
            {meta?.scenarios.map((s) => (
              <button key={s.id} className="starter" onClick={() => onAsk(s.id)}>
                <span className="starter-tag">{tagOf(s.title)}</span>
                <span className="starter-q">{s.question}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
      <TreeArt />
    </section>
  );
}
