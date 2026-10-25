import { useState } from "react";
import { useTree } from "../../context/TreeContext";
import { matchQuestion } from "./chatUtils";

/** A real message box. This demo only knows its sample questions, so anything else gets a plain explanation. */
export function Composer({ onAsk, placeholder, autoFocus }: { onAsk: (id: string) => void; placeholder: string; autoFocus?: boolean }) {
  const { meta } = useTree();
  const [text, setText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const submit = () => {
    if (!text.trim() || !meta) return;
    const id = matchQuestion(text, meta.scenarios);
    if (id) {
      setText("");
      setNotice(null);
      onAsk(id);
    } else {
      setNotice("This demo only answers its sample questions. Pick one below, or type it as shown.");
    }
  };

  return (
    <div className="composer-box">
      <form
        className="composer-input"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          aria-label="Message the OCBC assistant"
          autoFocus={autoFocus}
        />
        <button type="submit" className="send" aria-label="Send" disabled={!text.trim()}>
          ➤
        </button>
      </form>
      {notice && <p className="composer-notice" role="status">{notice}</p>}
    </div>
  );
}
