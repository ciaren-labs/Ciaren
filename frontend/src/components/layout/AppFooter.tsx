import { Github } from "lucide-react";

export function AppFooter() {
  return (
    <footer className="flex shrink-0 items-center justify-between border-t border-border bg-background/80 px-5 py-2 text-[11px] text-muted-foreground backdrop-blur">
      <span>
        <span className="font-medium text-brand-600">Flow</span>
        <span>Frame</span>
        {" — "}open-core local-first ETL builder
      </span>
      <div className="flex items-center gap-4">
        <a
          href="https://github.com/rodrigo-arenas/flowframe"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 transition-colors hover:text-foreground"
        >
          <Github className="h-3 w-3" /> GitHub
        </a>
        <a
          href="https://github.com/rodrigo-arenas/flowframe#readme"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-colors hover:text-foreground"
        >
          Docs
        </a>
        <a
          href="https://github.com/rodrigo-arenas/flowframe/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-colors hover:text-foreground"
        >
          Report issue
        </a>
      </div>
    </footer>
  );
}
