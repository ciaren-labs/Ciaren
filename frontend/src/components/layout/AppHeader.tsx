import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Flows" },
  { to: "/datasets", label: "Datasets" },
];

export function AppHeader() {
  const { pathname } = useLocation();
  return (
    <header className="flex h-12 items-center gap-6 border-b border-border bg-background px-4">
      <Link to="/" className="text-sm font-bold">
        FlowFrame
      </Link>
      <nav className="flex items-center gap-4">
        {NAV.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "text-sm text-muted-foreground hover:text-foreground",
              pathname === item.to && "font-medium text-foreground",
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
