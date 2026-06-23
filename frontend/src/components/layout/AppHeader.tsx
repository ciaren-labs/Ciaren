import { Link, useLocation } from "react-router-dom";
import {
  CalendarClock,
  Database,
  FolderKanban,
  Globe,
  History,
  Plug,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTimezoneStore, COMMON_TIMEZONES } from "@/stores/timezoneStore";
import { SearchableSelect } from "@/components/filters/SearchableSelect";

const NAV = [
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/datasets", label: "Datasets", icon: Database },
  { to: "/connections", label: "Connections", icon: Plug },
  { to: "/flows", label: "Flows", icon: Workflow },
  { to: "/schedules", label: "Schedules", icon: CalendarClock },
  { to: "/runs", label: "Runs", icon: History },
];

function isActive(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function AppHeader() {
  const { pathname } = useLocation();
  const { timezone, setTimezone } = useTimezoneStore();

  return (
    <header className="flex h-14 items-center gap-6 border-b border-border bg-background/80 px-5 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <Link to="/" className="flex items-center gap-2 font-bold tracking-tight shrink-0">
        <span className="brand-gradient flex h-7 w-7 items-center justify-center rounded-lg text-white shadow-sm shadow-brand-600/30">
          <Workflow className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <span className="text-[15px]">
          <span className="text-brand-600">Flow</span>
          <span className="text-muted-foreground">Frame</span>
        </span>
      </Link>
      <nav className="flex items-center gap-1">
        {NAV.map((item) => {
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
    </header>
  );
}
