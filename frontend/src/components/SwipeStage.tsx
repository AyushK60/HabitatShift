/** Georeferenced before/after swipe stage with hover-follow divider.
 *
 * Interaction contract (M3 brief §6):
 * - Desktop mouse: the divider follows the cursor's horizontal position while
 *   it moves across the stage — no click needed.
 * - The split is NOT reset when the cursor exits.
 * - Touch/pen keep classic press-and-drag; hover tracking is mouse-only so it
 *   cannot interfere with touch.
 * - Keyboard: the divider is a `role="slider"`; ←/→ (and ↑/↓) step 1 %,
 *   Shift+arrow steps 10 %, PageUp/PageDown 10 %, Home/End go to the edges.
 * - A visible reset control returns to 50 %; double-click also resets.
 * - Updates are coalesced with requestAnimationFrame to avoid jitter.
 *
 * Both images share one stage and therefore one geographic frame; the later
 * period is a clipped overlay so the two rasters stay exactly registered.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface SwipeImageSpec {
  src: string;
  alt: string;
}

interface SwipeStageProps {
  earlier: SwipeImageSpec;
  later: SwipeImageSpec;
  aspectRatio: string;
  initialSplit?: number;
  /** Printed in the tools row; keep it honest about what is being compared. */
  hint?: string;
  className?: string;
  /** Hide the tools row (e.g. for the compact landing hero). */
  showTools?: boolean;
  onSplitChange?: (split: number) => void;
}

export function SwipeStage({
  earlier,
  later,
  aspectRatio,
  initialSplit = 50,
  hint,
  className,
  showTools = true,
  onSplitChange,
}: SwipeStageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const splitRef = useRef(initialSplit);
  const rafRef = useRef<number | null>(null);
  const draggingRef = useRef(false);
  const [splitLabel, setSplitLabel] = useState(initialSplit);
  const [missing, setMissing] = useState<string | null>(null);

  const apply = useCallback(
    (value: number) => {
      const next = Math.min(100, Math.max(0, value));
      splitRef.current = next;
      if (rafRef.current !== null) return; // coalesce to one frame
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const stage = stageRef.current;
        if (stage) {
          stage.style.setProperty("--split", `${splitRef.current}%`);
          const rounded = Math.round(splitRef.current);
          const divider = stage.querySelector<HTMLDivElement>(".swipe-divider");
          if (divider) {
            divider.setAttribute("aria-valuenow", String(rounded));
            divider.setAttribute(
              "aria-valuetext",
              `${rounded}% earlier, ${100 - rounded}% later`
            );
          }
        }
        setSplitLabel(Math.round(splitRef.current));
        onSplitChange?.(splitRef.current);
      });
    },
    [onSplitChange]
  );

  useEffect(() => {
    const stage = stageRef.current;
    if (stage) stage.style.setProperty("--split", `${splitRef.current}%`);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const splitFromEvent = (clientX: number): number | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const box = stage.getBoundingClientRect();
    if (!box.width) return null;
    return ((clientX - box.left) / box.width) * 100;
  };

  /* Hover-follow: mouse movement across the stage moves the divider with no
   * button held. Only `pointerType === "mouse"`; touch/pen use drag below. */
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse" && !draggingRef.current) return;
    if (event.pointerType === "mouse" && draggingRef.current) {
      // While a mouse button is held the drag path below already applies the
      // same update; nothing extra to do here.
    }
    if (event.pointerType !== "mouse" && event.buttons === 0) return;
    const value = splitFromEvent(event.clientX);
    if (value !== null) apply(value);
  };

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    // Mouse users already get hover-follow; press-drag remains for touch/pen
    // and also re-anchors immediately on click for mouse users.
    event.preventDefault();
    draggingRef.current = true;
    stageRef.current?.classList.add("is-dragging");
    const value = splitFromEvent(event.clientX);
    if (value !== null) apply(value);
    const stage = stageRef.current;
    if (stage?.hasPointerCapture?.(event.pointerId) === false) {
      try {
        stage.setPointerCapture(event.pointerId);
      } catch {
        /* pointer capture is best-effort */
      }
    }
  };

  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    stageRef.current?.classList.remove("is-dragging");
    const stage = stageRef.current;
    if (stage?.hasPointerCapture?.(event.pointerId)) {
      stage.releasePointerCapture(event.pointerId);
    }
  };

  const onDividerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    let next = splitRef.current;
    const step = event.shiftKey ? 10 : 1;
    switch (event.key) {
      case "ArrowLeft":
      case "ArrowDown":
        next -= step;
        break;
      case "ArrowRight":
      case "ArrowUp":
        next += step;
        break;
      case "PageDown":
        next -= 10;
        break;
      case "PageUp":
        next += 10;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = 100;
        break;
      default:
        return;
    }
    event.preventDefault();
    apply(next);
  };

  const imageError = (message: string) => () => setMissing(message);

  return (
    <figure className={`swipe-figure ${className ?? ""}`.trim()}>
      <div
        ref={stageRef}
        className="swipe-stage"
        style={{ aspectRatio, ["--split" as string]: `${initialSplit}%` }}
        onPointerMove={onPointerMove}
        onPointerDown={onPointerDown}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={(event) => {
          event.preventDefault();
          apply(50);
        }}
        data-missing={missing ?? undefined}
      >
        <img
          src={earlier.src}
          alt={earlier.alt}
          decoding="async"
          data-role="earlier"
          onError={imageError("Earlier preview unavailable")}
        />
        <div className="swipe-later">
          <img
            src={later.src}
            alt={later.alt}
            decoding="async"
            data-role="later"
            onError={imageError("Later preview unavailable")}
          />
        </div>
        <div
          className="swipe-divider"
          role="slider"
          tabIndex={0}
          aria-label="Before/after comparison divider"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={initialSplit}
          aria-valuetext={`${initialSplit}% earlier, ${100 - initialSplit}% later`}
          onKeyDown={onDividerKeyDown}
        >
          <span className="swipe-divider-line" aria-hidden="true" />
          <span className="swipe-divider-grip" aria-hidden="true" />
        </div>
        {missing && (
          <span className="swipe-missing-note" role="status">
            {missing}
          </span>
        )}
      </div>
      {showTools && (
        <figcaption className="swipe-tools">
          <span className="swipe-hint">
            {hint ?? "Move the cursor across the image to trace the divider; arrow keys work when the divider is focused."}
          </span>
          <span className="swipe-readout" aria-hidden="true">
            {splitLabel}% earlier / {100 - splitLabel}% later
          </span>
          <button
            type="button"
            className="swipe-reset"
            onClick={() => apply(50)}
          >
            Reset 50%
          </button>
        </figcaption>
      )}
    </figure>
  );
}
