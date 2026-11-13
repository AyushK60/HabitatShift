/** Site-wide guided tour. Walks through the real pages in order, in plain words: each step opens a page, scrolls to
 *  the part being described and rings it. Keyboard: arrows move, Esc closes. Nothing here computes a result. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

interface Step {
  route: string;
  target?: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    route: "/",
    target: "hero",
    title: "What this is",
    body: "HabitatShift watches the land from space and asks one careful question: is this change real, or just the normal difference between two pictures? Everything on this site comes from open Sentinel satellite data.",
  },
  {
    route: "/",
    target: "question",
    title: "The research question",
    body: "New AI models for satellite images claim to spot change better than simple formulas. We test that claim fairly, by judging both against the same everyday noise, and we report the result even when it is not flattering.",
  },
  {
    route: "/research",
    target: "findings",
    title: "What we found",
    body: "Three results. For forest loss, a simple vegetation formula was as good as the AI models. For lakes, the models did better than the water formula. A small radar model agrees with optical maps, but its error bars do not carry over to new lakes.",
  },
  {
    route: "/lakes",
    target: "lake-chart",
    title: "Are the glacial lakes growing?",
    body: "Each card gives the answer for one lake in a single line, from radar that sees through monsoon cloud. Click a lake for its real before and after pictures and a yearly chart.",
  },
  {
    route: "/experiments",
    target: "exp-pick",
    title: "Evidence for each study area",
    body: "Pick a study area to see its numbers. Each graph has a short plain-words note underneath, and a technical note if you want the method.",
  },
  {
    route: "/workstation",
    target: "ws-pick",
    title: "The workstation",
    body: "Open any study area to slide between before and after images on a map, switch layers, and see which changed areas are bigger than the noise.",
  },
  {
    route: "/availability",
    target: "scene-form",
    title: "Scene check",
    body: "Before running a study anywhere, check which clear satellite images exist for that place and time. No clear scenes means no honest answer.",
  },
  {
    route: "/system",
    target: "system-stats",
    title: "What sits behind it",
    body: "These counts come from the files the pipeline wrote: scenes searched, radar and optical pairs kept, models trained, tests that guard the code. It is the proof of work behind every graph.",
  },
  {
    route: "/methods",
    title: "Methods and limits",
    body: "How each number is made, what data was used, and what this work cannot show. This is the page to open when someone asks how you know.",
  },
];

export function TourOverlay({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const navigate = useNavigate();
  const step = STEPS[index];
  const nextRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    navigate(step.route);
    let ring: Element | null = null;
    const timer = window.setTimeout(() => {
      if (!step.target) return;
      ring = document.querySelector(`[data-tour="${step.target}"]`);
      if (ring) {
        ring.scrollIntoView({ behavior: "smooth", block: "center" });
        ring.classList.add("tour-spot");
      }
    }, 450);
    return () => {
      window.clearTimeout(timer);
      ring?.classList.remove("tour-spot");
      document.querySelectorAll(".tour-spot").forEach((el) => el.classList.remove("tour-spot"));
    };
  }, [index]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    nextRef.current?.focus({ preventScroll: true });
  }, [index]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") setIndex((i) => Math.min(STEPS.length - 1, i + 1));
      if (event.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const last = index === STEPS.length - 1;
  return (
    <aside className="tour" role="dialog" aria-modal="false" aria-labelledby="tour-title" data-testid="site-tour">
      <div className="tour-dots" aria-hidden="true">
        {STEPS.map((_, i) => (
          <span key={i} className={i === index ? "is-on" : i < index ? "is-done" : ""} />
        ))}
      </div>
      <p className="tour-count">
        Step {index + 1} of {STEPS.length}
      </p>
      <h2 id="tour-title">{step.title}</h2>
      <p className="tour-body">{step.body}</p>
      <div className="tour-actions">
        <button type="button" className="tour-quiet" onClick={onClose}>
          Leave tour
        </button>
        <span className="tour-spacer" />
        <button type="button" className="tour-btn" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          Back
        </button>
        <button
          ref={nextRef}
          type="button"
          className="tour-btn is-primary"
          onClick={() => (last ? onClose() : setIndex(index + 1))}
        >
          {last ? "Finish" : "Next"}
        </button>
      </div>
    </aside>
  );
}
