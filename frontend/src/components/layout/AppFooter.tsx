import { ExternalLink, Github } from "lucide-react";

const WEBSITE_URL = "https://www.ciaren.com";
const REPO_URL = "https://github.com/ciaren-labs/Ciaren";
const DOCS_URL = "https://ciaren.com/docs";

export function AppFooter() {
  return (
    <footer className="flex shrink-0 items-center justify-between border-t border-border bg-background/80 px-6 py-3 text-xs text-muted-foreground backdrop-blur">
      <span>
        <span className="font-medium text-brand-600">Ciaren</span>
        {" — "}open-core local-first data and ML workflow builder
      </span>
      <div className="flex items-center gap-4">
        <a
          href={WEBSITE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 transition-colors hover:text-foreground"
        >
          <ExternalLink className="h-3.5 w-3.5" /> Website
        </a>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 transition-colors hover:text-foreground"
        >
          <Github className="h-3.5 w-3.5" /> GitHub
        </a>
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="transition-colors hover:text-foreground"
        >
          Docs
        </a>
        <a
          href={`${REPO_URL}/issues`}
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
