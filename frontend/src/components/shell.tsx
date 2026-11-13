/** Product shell: top navigation and footer, shared by every page. */
import { useEffect, useState } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { AudienceSwitch } from "./audience";

const NAV_ITEMS = [
  { to: "/research", label: "Research" },
  { to: "/lakes", label: "Glacial lakes" },
  { to: "/experiments", label: "Evidence" },
  { to: "/workstation", label: "Workstation" },
  { to: "/availability", label: "Scene check" },
  { to: "/system", label: "System" },
  { to: "/methods", label: "Methods" },
];

export function TopNav({ onStartTour }: { onStartTour: () => void }) {
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > window.innerHeight * 0.6);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const over = pathname === "/" && !scrolled;
  return (
    <header className={over ? "topnav topnav--over" : "topnav"}>
      <div className="topnav-inner">
        <Link to="/" className="brand" aria-label="HabitatShift home">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">HabitatShift</span>
        </Link>
        <nav aria-label="Primary">
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                 
                  className={pathname === item.to || pathname.startsWith(item.to) ? "nav-link is-active" : "nav-link"}
                  aria-current={pathname === item.to ? "page" : undefined}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="nav-tools">
          <AudienceSwitch />
          <button type="button" className="tour-launch" onClick={onStartTour}>
            Guided tour
          </button>
        </div>
      </div>
    </header>
  );
}

export function Footer({ attribution }: { attribution?: string }) {
  return (
    <footer className="foot">
      <div className="foot-inner">
        <p className="foot-brand">
          <span className="brand-mark" aria-hidden="true" /> HabitatShift
        </p>
        <p>
          Landscape change from open Sentinel-1 radar and Sentinel-2 optical data, with every result shown next to its
          uncertainty. Results are agreement with a reference product, not measured accuracy.
        </p>
        <p>
          {attribution ??
            "Contains modified Copernicus Sentinel data, processed by ESA. Sentinel-2 via Element 84 Earth Search; Sentinel-1 and DEM via Microsoft Planetary Computer."}
        </p>
        <p>
          Methods, limits and data sources: <Link to="/methods">Methods</Link>.
        </p>
      </div>
    </footer>
  );
}
