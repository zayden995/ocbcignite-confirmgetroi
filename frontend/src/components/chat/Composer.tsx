import { useState } from "react";
import { useTree } from "../../context/TreeContext";
import { rateQuestion } from "../../assessment/types";
import { matchQuestion } from "./chatUtils";

/** Accepts both sample questions and any free-form custom question. */
export function Composer({
  onAsk,
  placeholder,
  autoFocus,
}: {
  onAsk: (id: string) => void;
  placeholder: string;
  autoFocus?: boolean;
}) {
  const { meta, askCustomQuestion } = useTree();
  const [text, setText] = useState("");

  const submit = async () => {
    if (!text.trim() || !meta) return;
    const q = text.trim();
    const id = q === rateQuestion ? "decision-rate" : q === meta.assessment_fixture.question ? "decision-plan" : matchQuestion(q, meta.scenarios);
    setText("");
    if (id) {
      onAsk(id);
    } else {
      onAsk("custom");
      await askCustomQuestion(q);
    }
  };

  return (
    <div className="composer-box">
      <form
        className="composer-input"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          aria-label="Message the OCBC assistant"
          autoFocus={autoFocus}
        />
        <button type="submit" className="send" aria-label="Send" disabled={!meta || !text.trim()}>
          ➤
        </button>
      </form>

    </div>
  );
}