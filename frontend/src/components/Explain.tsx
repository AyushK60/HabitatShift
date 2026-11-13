/** Explanation block that sits under a graph or table: one line of plain words, and a technical note.
 *  The top-bar audience switch chooses which is open; the other stays one click away. */
import { useState, type ReactNode } from "react";
import { useAudience } from "./audience";

interface Props {
  /** The takeaway for a first-time reader, one or two sentences. */
  plain: ReactNode;
  /** How the number was made, with terms and caveats. */
  technical?: ReactNode;
  /** What to look at, e.g. "Each dot is one month." */
  howToRead?: ReactNode;
}

export function Explain({ plain, technical, howToRead }: Props) {
  const { audience } = useAudience();
  const [flipped, setFlipped] = useState(false);
  const showTech = (audience === "technical") !== flipped && !!technical;
  return (
    <div className={`explain${showTech ? " is-technical" : ""}`}>
      <div className="explain-body">
        <p className="explain-label">{showTech ? "How it was made" : "In plain words"}</p>
        <div className="explain-text">{showTech ? technical : plain}</div>
        {howToRead && !showTech && <p className="explain-how">{howToRead}</p>}
      </div>
      {technical && (
        <button type="button" className="explain-flip" onClick={() => setFlipped((f) => !f)} aria-pressed={flipped}>
          {showTech ? "Show plain words" : "Show the method"}
        </button>
      )}
    </div>
  );
}
