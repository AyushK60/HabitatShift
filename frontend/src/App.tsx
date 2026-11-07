import { Route, Routes, useLocation } from "react-router-dom";
import { Footer, TopNav } from "./components/shell";
import { LandingPage } from "./pages/LandingPage";
import { WorkstationPage } from "./pages/WorkstationPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { MethodsPage } from "./pages/MethodsPage";

export default function App() {
  const { pathname } = useLocation();
  const isWorkstation = pathname.startsWith("/workstation");
  return (
    <div className={isWorkstation ? "app-shell app-shell--fixed" : "app-shell"}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <TopNav />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/workstation" element={<WorkstationPage />} />
        <Route path="/experiments" element={<ExperimentsPage />} />
        <Route path="/methods" element={<MethodsPage />} />
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
      {!isWorkstation && <Footer />}
    </div>
  );
}
