/** Audience switch: "Plain words" or "Technical". Every explainer reads the same setting, so one click in the top
 *  bar changes how every graph is described. Remembered in localStorage when available. */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Audience = "plain" | "technical";
const KEY = "habitatshift-audience";
const Ctx = createContext<{ audience: Audience; setAudience: (a: Audience) => void }>({
  audience: "plain",
  setAudience: () => {},
});

function initial(): Audience {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "plain" || saved === "technical") return saved;
  } catch {
    /* storage may be blocked */
  }
  return "plain";
}

export function AudienceProvider({ children }: { children: ReactNode }) {
  const [audience, setAudience] = useState<Audience>(initial);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, audience);
    } catch {
      /* ignore */
    }
    document.documentElement.dataset.audience = audience;
  }, [audience]);
  const value = useMemo(() => ({ audience, setAudience }), [audience]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAudience = () => useContext(Ctx);

export function AudienceSwitch() {
  const { audience, setAudience } = useAudience();
  return (
    <div className="audience" role="group" aria-label="Explanation level">
      <button type="button" aria-pressed={audience === "plain"} onClick={() => setAudience("plain")}>
        Plain words
      </button>
      <button type="button" aria-pressed={audience === "technical"} onClick={() => setAudience("technical")}>
        Technical
      </button>
    </div>
  );
}
