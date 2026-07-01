import { Link, useLocation } from "react-router-dom";
import {
  Blocks,
  BrainCircuit,
  CalendarClock,
  Database,
  FolderKanban,
  Globe,
  History,
  Moon,
  Plug,
  Sun,
  Workflow,
} from "lucide-react";
import ciarenSymbol from "@/assets/symbol-white.svg";
import { cn } from "@/lib/utils";
import { useTimezoneStore, COMMON_TIMEZONES } from "@/stores/timezoneStore";
import { useThemeStore } from "@/stores/themeStore";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useMlEnabled } from "@/features/models/hooks";

// Order: Connections first, then setup → build → run. Models slots in right
// after Flows (only when ML is enabled — see ML_NAV / nav assembly below).
const NAV_BEFORE_MODELS = [
  { to: "/connections", label: "Connections", icon: Plug },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/datasets", label: "Datasets", icon: Database },
  { to: "/flows", label: "Flows", icon: Workflow },
];
const NAV_AFTER_MODELS = [
  { to: "/schedules", label: "Schedules", icon: CalendarClock },
  { to: "/runs", label: "Runs", icon: History },
  { to: "/plugins", label: "Plugins", icon: Blocks },
];

// Shown only when ML is enabled (CIAREN_ML_ENABLED, on by default).
const ML_NAV = { to: "/models", label: "Models", icon: BrainCircuit };

function isActive(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function AppHeader() {
  const { pathname } = useLocation();
  const { timezone, setTimezone } = useTimezoneStore();
  const { theme, toggleTheme } = useThemeStore();
  const mlEnabled = useMlEnabled();
  const nav = [
    ...NAV_BEFORE_MODELS,
    ...(mlEnabled ? [ML_NAV] : []),
    ...NAV_AFTER_MODELS,
  ];

  return (
    <header className="flex h-14 items-center gap-6 border-b border-border bg-background/80 px-5 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <Link to="/" className="flex items-center gap-2 font-bold tracking-tight shrink-0">
        <span className="brand-gradient flex h-7 w-7 items-center justify-center rounded-lg shadow-sm shadow-brand-600/30">
          <img src={ciarenSymbol} alt="" className="h-4 w-4" />
        </span>
        <span className="text-[15px]">
          <span className="text-brand-600">Ciaren</span>
        </span>
      </Link>
      <nav className="flex items-center gap-1">
        {nav.map((item) => {
          const active = isActive(pathname, item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Timezone preference */}
      <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
        <Globe className="h-3.5 w-3.5 shrink-0" />
        <SearchableSelect
          value={timezone}
          onChange={setTimezone}
          allLabel="Browser default"
          placeholder="Search timezone…"
          className="w-56"
          options={COMMON_TIMEZONES.filter((tz) => tz.value !== "").map((tz) => ({
            value: tz.value,
            label: tz.label,
          }))}
        />
      </div>

      <button
        onClick={toggleTheme}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </header>
  );
}
