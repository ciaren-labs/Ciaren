import { Link, useLocation } from "react-router-dom";
import { Database, FolderKanban, History, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Flows", icon: Workflow },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/datasets", label: "Datasets", icon: Database },
  { to: "/runs", label: "Runs", icon: History },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/" || pathname.startsWith("/flows");
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function AppHeader() {
  const { pathname } = useLocation();
  return (
    <header className="flex h-14 items-center gap-6 border-b border-border bg-background/80 px-5 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <Link to="/" className="flex items-center gap-2 font-bold tracking-tight">
        <span className="brand-gradient flex h-7 w-7 items-center justify-center rounded-lg text-white shadow-sm shadow-brand-600/30">
          <Workflow className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <span className="brand-text-gradient text-[15px]">FlowFrame</span>
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
    </header>
  );
}
