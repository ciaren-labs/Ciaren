import { Link } from "react-router-dom";
import {
  ArrowRight,
  BrainCircuit,
  Code2,
  Database,
  FolderKanban,
  Github,
  Layers,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const REPO_URL = "https://github.com/rodrigo-arenas/Ciaren";
const DOCS_URL = "https://rodrigo-arenas.github.io/Ciaren";

const FEATURES = [
  {
    icon: Workflow,
    title: "Visual pipelines",
    body: "Drag nodes onto a canvas to build a cleaning pipeline — no code required to start.",
  },
  {
    icon: Code2,
    title: "polars or pandas, exported to Python",
    body: "Runs on polars by default (switch to pandas per run) and exports every flow to clean, runnable Python you can take anywhere.",
  },
  {
    icon: Database,
    title: "Versioned datasets",
    body: "Re-uploading a file keeps every version, so scheduled flows stay reproducible.",
  },
  {
    icon: Layers,
    title: "Live preview",
    body: "See the result of each step on real data before you run the whole pipeline.",
  },
  {
    icon: FolderKanban,
    title: "Projects",
    body: "Group related datasets and flows into tidy, shareable workspaces.",
  },
  {
    icon: BrainCircuit,
    title: "Machine learning",
    body: "Split, train, predict, and evaluate models on the canvas — tracked with MLflow. Optional extension.",
  },
];

const STEPS = [
  { n: 1, title: "Upload data", body: "Bring a CSV, Excel or Parquet file." },
  { n: 2, title: "Build visually", body: "Connect nodes to clean and transform it." },
  { n: 3, title: "Run & export", body: "Execute the flow and export readable Python." },
];

export function LandingPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      {/* Hero */}
      <section className="flex flex-col items-center text-center">
        <span className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          <Github className="h-3.5 w-3.5" /> Open-core · local-first
        </span>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          The simplest visual <span className="brand-text-gradient">data &amp; ML</span> builder
        </h1>
        <p className="mt-4 max-w-2xl text-base text-muted-foreground sm:text-lg">
          Build, run, and schedule data pipelines — and train machine-learning models — on a
          drag-and-drop canvas. Preview every step, execute with one click, and export readable
          Python when you need it. Built for data analysts, data engineers, and anyone who wants
          reproducible pipelines without the boilerplate.
        </p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link to="/flows">
              Get started <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <a href={DOCS_URL} target="_blank" rel="noreferrer">
              Read the docs
            </a>
          </Button>
          <Button asChild size="lg" variant="ghost">
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              <Github className="h-4 w-4" /> GitHub
            </a>
          </Button>
        </div>
      </section>

      {/* Steps */}
      <section className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {STEPS.map((s) => (
          <div key={s.n} className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <span className="brand-gradient flex h-8 w-8 items-center justify-center rounded-lg text-sm font-semibold text-white shadow-sm">
              {s.n}
            </span>
            <h3 className="mt-3 font-semibold">{s.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
          </div>
        ))}
      </section>

      {/* Features */}
      <section className="mt-12">
        <h2 className="text-center text-xl font-semibold">What Ciaren gives you</h2>
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="animate-fade-in-up rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
                <f.icon className="h-5 w-5" />
              </span>
              <h3 className="mt-3 font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="brand-gradient mt-14 flex flex-col items-center gap-4 rounded-2xl px-6 py-10 text-center text-white">
        <h2 className="text-2xl font-semibold">Build your first flow in minutes</h2>
        <p className="max-w-xl text-sm text-white/90">
          Ciaren runs locally — your data never leaves your machine.
        </p>
        <Button asChild size="lg" variant="secondary">
          <Link to="/flows">
            Open the editor <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </section>

      <footer className="mt-10 text-center text-xs text-muted-foreground">
        Ciaren Core is free and open ·{" "}
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="underline hover:text-foreground">
          Contribute on GitHub
        </a>
      </footer>
    </div>
  );
}
