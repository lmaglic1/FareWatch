import { useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Compare from "./pages/Compare";
import Dashboard from "./pages/Dashboard";
import Explore from "./pages/Explore";
import RoutePage from "./pages/Route";
import Trips from "./pages/Trips";

const NAV = [
  { to: "/", label: "Explore" },
  { to: "/trips", label: "My trips" },
  { to: "/compare", label: "Compare dates" },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="FareWatch home">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path d="M7 21l18-7-18-7 4 7-4 7z" fill="#fff" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink">FareWatch</span>
    </Link>
  );
}

export default function App() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-raised font-medium text-ink shadow-card" : "text-ink-2 hover:text-ink"}`;

  return (
    <div className="flex min-h-screen flex-col bg-plane">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 btn-primary">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-hair bg-plane">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />
          <nav className="hidden items-center gap-1 sm:flex">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"} className={linkCls}>{n.label}</NavLink>)}
          </nav>
          <button className="btn-ghost sm:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((o) => !o)}>
            {open ? "Close" : "Menu"}
          </button>
        </div>
        {open && (
          <nav id="mobile-nav" className="flex flex-col gap-1 border-t border-hair px-4 py-3 sm:hidden" onClick={() => setOpen(false)}>
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"} className={linkCls}>{n.label}</NavLink>)}
          </nav>
        )}
      </header>

      <main id="main" key={loc.pathname} className="relative z-10 mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-10">
        <Routes>
          <Route path="/" element={<Explore />} />
          <Route path="/trips" element={<Trips />} />
          <Route path="/trips/new-year" element={<Dashboard />} />
          <Route path="/route/:origin/:destination/:date" element={<RoutePage />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/flights/*" element={<Navigate to="/trips/new-year" replace />} />
          <Route path="*" element={<p className="text-sm text-ink-2">Page not found. <Link className="text-accent-ink" to="/">Go to Explore</Link></p>} />
        </Routes>
      </main>

      <footer className="border-t border-hair">
        <div className="mx-auto max-w-6xl px-4 py-5 text-[11px] leading-relaxed text-ink-3 sm:px-6">
          FareWatch shows real fares observed on Google Flights (via SerpApi) or entered by hand. It never books or pays,
          and it cannot guarantee the lowest price. Not affiliated with any airline or with Google.
        </div>
      </footer>
    </div>
  );
}
