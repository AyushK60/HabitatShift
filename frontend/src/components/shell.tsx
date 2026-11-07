/** Product shell: top navigation and footer, shared by every M3 page. */
import { NavLink, Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Atlas", end: true },
  { to: "/workstation", label: "Workstation" },
  { to: "/experiments", label: "Experiments" },
  { to: "/methods", label: "Methods" },
];

export function TopNav() {
  const { pathname } = useLocation();
  return (
    <header className="topnav">
      <div className="topnav-inner">
        <Link to="/" className="brand" aria-label="HabitatShift home">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">HabitatShift</span>
          <span className="brand-tag">Landscape-change research workstation</span>
        </Link>
        <nav aria-label="Primary">
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={
                    pathname === item.to ? "nav-link is-active" : "nav-link"
                  }
                  aria-current={pathname === item.to ? "page" : undefined}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
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
          Reproducible landscape-change evidence from open Sentinel-2 data.
          Imagery throughout this product is generated from real processed
          scenes; every measurement traces to a stored pipeline artefact.
        </p>
        <p>
          {attribution ??
            "Contains modified Copernicus Sentinel data, processed by ESA. L2A products via the Element 84 Earth Search STAC catalogue (AWS Open Data)."}
        </p>
        <p className="foot-licence">
          Sentinel-2 data: free and open with attribution (ESA Copernicus).
          Methods, limitations and provenance:{" "}
          <Link to="/methods">Methods &amp; exports</Link>. The legacy M0–M2
          proof viewer remains available at <code>/legacy</code>.
        </p>
      </div>
    </footer>
  );
}
