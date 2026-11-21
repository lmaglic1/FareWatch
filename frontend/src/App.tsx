import { useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import About from "./pages/About";
import Alerts from "./pages/Alerts";
import Compare from "./pages/Compare";
import Dashboard from "./pages/Dashboard";
import Extras from "./pages/Extras";
import FlightDetails from "./pages/FlightDetails";
import History from "./pages/History";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/flights", label: "Flight Details" },
  { to: "/compare", label: "Compare Flights" },
  { to: "/history", label: "Price History" },
  { to: "/alerts", label: "Alerts" },
  { to: "/extras", label: "Bags & Promotions" },
  { to: "/settings", label: "Settings" },
  { to: "/about", label: "About the Algorithm" },
];

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path d="M7 21l18-7-18-7 4 7-4 7z" fill="#fff" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink">FareWatch</span>
    </div>
  );
}

export default function App() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-raised font-medium text-ink shadow-card" : "text-ink-2 hover:text-ink"}`;

  return (
    <div className="min-h-screen bg-plane">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 btn-primary">
        Skip to content
      </a>
      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-hair bg-plane px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button className="btn-ghost" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((o) => !o)}>
          {open ? "Close" : "Menu"}
        </button>
      </header>
      {open && (
        <nav id="mobile-nav" className="border-b border-hair bg-plane px-4 pb-3 lg:hidden" onClick={() => setOpen(false)}>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={linkCls}>{n.label}</NavLink>
          ))}
        </nav>
      )}
      <div className="mx-auto flex max-w-7xl">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between px-4 py-6 lg:flex">
          <div>
            <div className="mb-8 px-3"><Logo /></div>
            <nav className="space-y-1">
              {NAV.map((n) => (
                <NavLink key={n.to} to={n.to} end={n.to === "/"} className={linkCls}>{n.label}</NavLink>
              ))}
            </nav>
          </div>
          <p className="px-3 text-[11px] leading-relaxed text-ink-3">
            Real observations only. FareWatch never books or pays and does not guarantee the lowest price.
          </p>
        </aside>
        <main id="main" key={loc.pathname} className="relative z-10 min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/flights" element={<FlightDetails />} />
            <Route path="/flights/:id" element={<FlightDetails />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/history" element={<History />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/extras" element={<Extras />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<p className="text-sm text-ink-2">Page not found.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
