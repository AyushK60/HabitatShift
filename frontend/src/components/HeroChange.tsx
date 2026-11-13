/** Home-page hero: the same place in October 2018 and October 2024, played as a short story that loops.
 *  1. 2018 with the lake outline from radar. 2. The picture fades to 2024. 3. The area that became lake is
 *  filled and labelled. Images are real Sentinel-2 scenes and the outlines are drawn from the radar water maps;
 *  both are produced by scripts/make_site_figures.py. */
import { useEffect, useRef, useState } from "react";

interface Fig {
  area_2018_km2: number;
  area_2024_km2: number;
  growth_centre: [number, number];
  size: [number, number];
}

const POSITION_Y = 0.88;
const TIMING = { hold2018: 3200, fade: 2600, hold2024: 6500, reset: 1400 };

export function HeroChange({ fig }: { fig: Fig }) {
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [phase, setPhase] = useState<0 | 1 | 2>(reduced ? 2 : 0);
  const [playing, setPlaying] = useState(!reduced);
  const box = useRef<HTMLDivElement>(null);
  const [mark, setMark] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useEffect(() => {
    if (!playing) return;
    const wait = phase === 0 ? TIMING.hold2018 : phase === 1 ? TIMING.fade + 600 : TIMING.hold2024;
    const timer = window.setTimeout(() => setPhase((p) => (p === 2 ? 0 : ((p + 1) as 1 | 2))), wait);
    return () => window.clearTimeout(timer);
  }, [phase, playing]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth, h = el.clientHeight;
      const [iw, ih] = fig.size;
      const scale = Math.max(w / iw, h / ih);
      const ox = (w - iw * scale) * 0.5;
      const oy = (h - ih * scale) * POSITION_Y;
      setMark({ x: ox + fig.growth_centre[0] * iw * scale, y: oy + fig.growth_centre[1] * ih * scale, w, h });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fig]);

  const jump = (p: 0 | 2) => {
    setPlaying(false);
    setPhase(p);
  };
  const grown = fig.area_2024_km2 - fig.area_2018_km2;
  const labelRight = mark ? mark.x < mark.w * 0.55 : true;
  return (
    <div className={`hc hc-p${phase}`} ref={box}>
      <img className="hc-img" src="./hero/imja_2018.jpg" alt="Imja Tsho, Nepal, October 2018, Sentinel-2 true colour" />
      <img className="hc-img hc-late" src="./hero/imja_2024.jpg" alt="Imja Tsho, Nepal, October 2024, Sentinel-2 true colour" />
      <img className="hc-img hc-ov hc-ov18" src="./figures/imja_outline_2018.png" alt="" aria-hidden="true" />
      <img className="hc-img hc-ov hc-ov24" src="./figures/imja_outline_2024.png" alt="" aria-hidden="true" />
      <div className="hc-shade" aria-hidden="true" />

      {mark && (
        <div className="hc-note" style={{ left: mark.x, top: mark.y }} aria-live="polite">
          <span className="hc-ring" aria-hidden="true" />
          <div className={`hc-label${labelRight ? " is-right" : " is-left"}`}>
            <b>+{grown.toFixed(1)} km²</b>
            <span>of new lake since 2018, from radar</span>
          </div>
        </div>
      )}

      <div className="hc-caption">
        <p className="hc-place">Imja Tsho, Nepal</p>
        <div className="hc-controls" role="group" aria-label="Year">
          <button type="button" className={phase === 0 ? "on" : ""} onClick={() => jump(0)}>Oct 2018</button>
          <button type="button" className={phase !== 0 ? "on" : ""} onClick={() => jump(2)}>Oct 2024</button>
          <button type="button" className="hc-play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause the animation" : "Play the animation"}>
            {playing ? "Pause" : "Play"}
          </button>
        </div>
        <p className="hc-read">
          Radar water maps: {fig.area_2018_km2.toFixed(1)} km² in 2018, {fig.area_2024_km2.toFixed(1)} km² in 2024. White line is the 2018
          shore; shaded area is lake that was not there before.
        </p>
        <p className="hc-credit">Sentinel-2 true colour. Contains modified Copernicus Sentinel data.</p>
      </div>
    </div>
  );
}
