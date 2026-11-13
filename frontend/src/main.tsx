import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/hanken-grotesk";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./styles/explain.css";
import "./styles/tour.css";
import "./styles/swipe.css";
import "./styles/landing.css";
import "./styles/experiments.css";
import "./styles/methods.css";
import "./styles/workstation.css";
import "./styles/pages.css";
import "./styles/system.css";
import App from "./App";
import { AudienceProvider } from "./components/audience";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <AudienceProvider>
        <App />
      </AudienceProvider>
    </HashRouter>
  </StrictMode>
);
