/** Site-wide cinematic tour, about 60 seconds. An opening title, six beats and a closing screen. Each beat opens the real
 *  page, dims everything except the part being described, and says one big sentence. The lake beat counts up a number
 *  computed from the same data the lakes page uses. Keyboard: arrows move, Esc closes. Nothing here computes a result. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { summarise, yearly, type LakeLike } from "./LakeSummary";

interface Beat {
  route: string;
  target?: string;
  chapter: string;
  headline: string;
  body: string;
  stat?: "imja";
}

const BEATS: Beat[] = [
  {
    route: "/", target: "hero", chapter: "The question",
    headline: "Is this change real, or just two different pictures?",
    body: "Two satellite photos never match exactly. We judge every change against that everyday noise before we call it real, and we report the result even when it is not flattering.",
  },
  {
    route: "/lakes", target: "lake-chart", chapter: "Glacial lakes", stat: "imja",
    headline: "Imja Tsho grew",
    body: "Radar sees through monsoon cloud, so each lake gets a one-line answer for 2017 to 2026. Only changes bigger than the normal month-to-month wobble are reported.",
  },
  {
    route: "/research", target: "findings", chapter: "Findings",
    headline: "A simple formula matched the AI for forest loss",
    body: "For lakes the AI models did better than the water formula. A small radar model agrees with optical maps, but its error bars do not carry over to new lakes.",
  },
  {
    route: "/workstation", target: "ws-pick", chapter: "Workstation",
    headline: "Slide between before and after, on a real map",
    body: "Open any study area, switch layers, and see which changed areas are bigger than the noise.",
  },
  {
    route: "/availability", target: "scene-form", chapter: "Scene check",
    headline: "Check the sky before you trust a map",
    body: "Pick a place and a season to see how many clear satellite photos exist. No clear photos means no honest answer.",
  },
  {
    route: "/methods", chapter: "Methods and limits",
    headline: "Every method and every limit, in the open",
    body: "How each number is made, what data was used, and what this work cannot show. Open it when someone asks how you know.",
  },
];

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** Counts from 0 to `to` once per `key`, or jumps straight there for reduced motion. */
function useCountUp(to: number | null, key: number): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (to === null) return;
    if (reducedMotion()) { setV(to); return; }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / 1400);
      setV(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, key]);
  return v;
}

/** Follows an element's box so a cut-out can be drawn around it, even while the page scrolls. */
function useRect(selector: string | undefined, key: number): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    setRect(null);
    if (!selector) return;
    let raf = 0;
    let el: Element | null = null;
    const start = window.setTimeout(() => {
      el = document.querySelector(`[data-tour="${selector}"]`);
      if (!el) return;
      (el as HTMLElement).style.scrollMarginTop = "96px";
      el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
      let last = "";
      const follow = () => {
        const r = el!.getBoundingClientRect();
        const sig = `${Math.round(r.top)}|${Math.round(r.left)}|${Math.round(r.width)}|${Math.round(r.height)}`;
        if (sig !== last) { last = sig; setRect(r); }
        raf = requestAnimationFrame(follow);
      };
      follow();
    }, 500);
    return () => { window.clearTimeout(start); cancelAnimationFrame(raf); };
  }, [selector, key]);
  return rect;
}

export function TourOverlay({ onClose }: { onClose: () => void }) {
  // -1 is the opening screen, BEATS.length is the closing screen.
  const [index, setIndex] = useState(-1);
  const [imjaPct, setImjaPct] = useState<number | null>(null);
  const navigate = useNavigate();
  const nextRef = useRef<HTMLButtonElement>(null);
  const beat = index >= 0 && index < BEATS.length ? BEATS[index] : null;
  const intro = index === -1;
  const outro = index === BEATS.length;

  useEffect(() => {
    fetch("lakes/lakes.json").then((r) => r.json()).then((b: { lakes: LakeLike[] }) => {
      const imja = b.lakes.find((l) => l.id === "imja_tsho");
      const s = imja ? summarise(yearly(imja.s1_monthly, 6)) : null;
      if (s && s.clear) setImjaPct(s.pct);
    }).catch(() => undefined);
  }, []);

  useEffect(() => { if (beat) navigate(beat.route); }, [index]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { nextRef.current?.focus({ preventScroll: true }); }, [index]);

  const rect = useRect(beat?.target, index);
  const counted = useCountUp(beat?.stat === "imja" ? imjaPct : null, index);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") setIndex((i) => Math.min(BEATS.length, i + 1));
      if (event.key === "ArrowLeft") setIndex((i) => Math.max(-1, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const pad = 12;
  return (
    <div className="tour-root" data-testid="tour-root">
      {beat && rect && (
        <div className="tour-hole" aria-hidden="true"
             style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }} />
      )}
      {beat && !rect && <div className="tour-veil" aria-hidden="true" />}

      {(intro || outro) && (
        <div className="tour-veil is-full" aria-hidden="true" />
      )}

      {intro && (
        <section className="tour-stage" role="dialog" aria-modal="true" aria-labelledby="tour-title" data-testid="site-tour">
          <p className="tour-kicker">HabitatShift · 60-second tour</p>
          <h2 id="tour-title" className="tour-giant">Is the change real?</h2>
          <p className="tour-lede">Six stops through what this project found, from glacial lakes in Nepal to forests in central India.</p>
          <div className="tour-actions">
            <button ref={nextRef} type="button" className="tour-btn is-primary is-large" onClick={() => setIndex(0)}>Start the tour</button>
            <button type="button" className="tour-quiet is-light" onClick={onClose}>Skip</button>
          </div>
        </section>
      )}

      {outro && (
        <section className="tour-stage" role="dialog" aria-modal="true" aria-labelledby="tour-title" data-testid="site-tour">
          <p className="tour-kicker">That was the tour</p>
          <h2 id="tour-title" className="tour-giant">Now try it yourself</h2>
          <p className="tour-lede">Every number you saw sits next to its uncertainty and the checks behind it.</p>
          <div className="tour-actions">
            <button ref={nextRef} type="button" className="tour-btn is-primary is-large" onClick={() => { navigate("/lakes"); onClose(); }}>Explore the lakes</button>
            <button type="button" className="tour-btn is-light" onClick={() => { navigate("/availability"); onClose(); }}>Run a scene check</button>
            <button type="button" className="tour-quiet is-light" onClick={onClose}>Close</button>
          </div>
        </section>
      )}

      {beat && (
        <aside className="tour-card" role="dialog" aria-modal="false" aria-labelledby="tour-title" data-testid="site-tour" key={index}>
          <p className="tour-chapter">{index + 1} of {BEATS.length} · {beat.chapter}</p>
          <h2 id="tour-title" className="tour-headline">
            {beat.headline}
            {beat.stat === "imja" && imjaPct !== null && (
              <span className="tour-stat"> {counted >= 0 ? "+" : ""}{Math.round(counted)}%</span>
            )}
          </h2>
          <p className="tour-body">{beat.body}</p>
          <ol className="tour-rail" aria-label="Tour progress">
            {BEATS.map((b, i) => (
              <li key={b.chapter} className={i === index ? "is-on" : i < index ? "is-done" : ""}>
                <button type="button" onClick={() => setIndex(i)} aria-label={`Go to ${b.chapter}`} aria-current={i === index ? "step" : undefined}><span /></button>
              </li>
            ))}
          </ol>
          <div className="tour-actions">
            <button type="button" className="tour-quiet" onClick={onClose}>Leave tour</button>
            <span className="tour-spacer" />
            <button type="button" className="tour-btn" onClick={() => setIndex(index - 1)}>Back</button>
            <button ref={nextRef} type="button" className="tour-btn is-primary" onClick={() => setIndex(index + 1)}>
              {index === BEATS.length - 1 ? "Finish" : "Next"}
            </button>
          </div>
        </aside>
      )}
    </div>
  );
}
