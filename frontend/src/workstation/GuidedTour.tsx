/** Guided tour ("story mode") for the workstation.
 *
 * A short, keyboard-operable walkthrough that drives the real controls
 * (analysis tabs, the analysis dock, the guide tab) and explains each stage in
 * plain language. Copy is generic and framing-safe: it describes what each view
 * shows and what it cannot conclude, using the study's own recorded
 * "cannot conclude" statements. No measurement is computed here.
 */
import { useEffect, useRef, useState } from "react";

export interface TourStep {
  title: string;
  body: string;
  /** Called when the step becomes active, to put the UI in the right state. */
  enter: () => void;
}

interface Props {
  steps: TourStep[];
  onClose: () => void;
}

export function GuidedTour({ steps, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const step = steps[index];
  const nextRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    step.enter();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  useEffect(() => {
    nextRef.current?.focus();
  }, [index]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const last = index === steps.length - 1;
  return (
    <aside className="guided-tour" role="dialog" aria-modal="false" aria-labelledby="tour-title" data-testid="guided-tour">
      <p className="mono-label">
        Guided tour · step {index + 1} of {steps.length}
      </p>
      <h2 id="tour-title">{step.title}</h2>
      <p>{step.body}</p>
      <div className="guided-tour-actions">
        <button type="button" className="toggle-btn" onClick={onClose}>
          Close tour
        </button>
        <button type="button" className="toggle-btn" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          Back
        </button>
        <button
          ref={nextRef}
          type="button"
          className="toggle-btn is-active"
          onClick={() => (last ? onClose() : setIndex(index + 1))}
        >
          {last ? "Finish" : "Next"}
        </button>
      </div>
    </aside>
  );
}
