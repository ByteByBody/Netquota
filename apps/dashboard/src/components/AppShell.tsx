import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/devices", label: "Devices" },
  { to: "/groups", label: "Groups" },
  { to: "/settings", label: "Settings" },
];

function Wordmark() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect x="2" y="2" width="28" height="28" rx="7" fill="none" stroke="currentColor" strokeWidth="2" className="text-signal" />
        {/* meter glyph */}
        <rect x="8" y="19" width="4" height="6" rx="1" fill="currentColor" className="text-signal" />
        <rect x="14" y="14" width="4" height="11" rx="1" fill="currentColor" className="text-signal/70" />
        <rect x="20" y="8" width="4" height="17" rx="1" fill="currentColor" className="text-signal/40" />
      </svg>
      <span className="font-display text-lg font-semibold tracking-tight">
        NetQuota
      </span>
    </div>
  );
}

export function AppShell() {
  const { logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-line bg-paper/80 backdrop-blur dark:bg-[#0F1519]/85">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <NavLink to="/" aria-label="NetQuota home">
            <Wordmark />
          </NavLink>
          <nav className="hidden items-center gap-1 sm:flex" aria-label="Primary">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-signal/10 text-signal"
                      : "text-muted hover:text-ink dark:hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              className="rounded-md border border-line px-2.5 py-1.5 text-sm text-muted hover:text-ink dark:hover:text-white"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <button
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="rounded-md border border-line px-2.5 py-1.5 text-sm text-muted hover:text-ink dark:hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-4 pb-2 sm:hidden" aria-label="Primary mobile">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${
                  isActive ? "bg-signal/10 text-signal" : "text-muted"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2 text-xs text-faint sm:px-6">
        Totals are device-reported usage, not guaranteed ISP-billed usage. NetQuota
        never blocks or throttles traffic.
      </footer>
    </div>
  );
}