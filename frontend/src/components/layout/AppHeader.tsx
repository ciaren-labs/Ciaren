import { Link, useLocation } from "react-router-dom";
import { Database, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Flows", icon: Workflow },
  { to: "/datasets", label: "Datasets", icon: Database },
];

export function AppHeader() {
  const { pathname } = useLocation();
  return (
    <header className="flex h-14 items-center gap-6 border-b border-border bg-background/80 px-5 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <Link to="/" className="flex items-center gap-2 font-bold tracking-tight">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <Workflow className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <span className="text-[15px]">FlowFrame</span>
      </Link>
      <nav className="flex items-center gap-1">
        {NAV.map((item) => {
          const active = pathname === item.to;
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
    </header>
  );
}
