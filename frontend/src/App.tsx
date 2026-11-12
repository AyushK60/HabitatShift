import { Suspense, lazy } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { Footer, TopNav } from "./components/shell";
import { LandingPage } from "./pages/LandingPage";

// Route-level code splitting: the landing page no longer downloads MapLibre and
// the workstation code (the single 1.5 MB bundle was the main load cost).
const WorkstationPage = lazy(() =>
  import("./pages/WorkstationPage").then((m) => ({ default: m.WorkstationPage }))
);
const ExperimentsPage = lazy(() =>
  import("./pages/ExperimentsPage").then((m) => ({ default: m.ExperimentsPage }))
);
const MethodsPage = lazy(() =>
  import("./pages/MethodsPage").then((m) => ({ default: m.MethodsPage }))
);

const AvailabilityPage = lazy(() =>
  import("./pages/AvailabilityPage").then((m) => ({ default: m.AvailabilityPage }))
);

function RouteFallback() {
  return (
    <main id="main" style={{ padding: "3rem 1.5rem" }} aria-busy="true">
      <p className="mono-label">Loading…</p>
    </main>
  );
}

export default function App() {
  const { pathname } = useLocation();
  // M4-R1 §2: /workstation without a study id is the study-selection
  // experience — a normal scrolling page, not the fixed-height workstation.
  const isWorkstation =
    pathname.startsWith("/workstation") && pathname !== "/workstation";
  return (
    <div className={isWorkstation ? "app-shell app-shell--fixed" : "app-shell"}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <TopNav />
      <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/workstation/:studyId?" element={<WorkstationPage />} />
        <Route path="/experiments" element={<ExperimentsPage />} />
        <Route path="/methods" element={<MethodsPage />} />
        <Route path="/availability" element={<AvailabilityPage />} />
        <Route
          path="*"
          element={
            <main id="main" style={{ padding: "3rem 1.5rem" }}>
              <h1>Page not found</h1>
              <p>The address does not match any HabitatShift page.</p>
            </main>
          }
        />
      </Routes>
      </Suspense>
      {!isWorkstation && <Footer />}
    </div>
  );
}
