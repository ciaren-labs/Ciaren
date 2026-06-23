# FlowFrame Documentation

User-facing documentation site built with VitePress and deployed to GitHub Pages.

## Project Summary

This is the official documentation for FlowFrame — a visual ETL builder. The docs are:

- **User-focused** — for analysts, developers, educators
- **Example-driven** — every feature has walkthroughs and sample data
- **Beginner-friendly** — explains concepts clearly
- **Searchable** — fast full-text search built-in

Published at: `https://rodrigo-arenas.github.io/FlowFrame`

---

## Documentation Vision

**Goal:** Make FlowFrame easy to learn and use through clear, example-rich documentation.

**Audience:**

- Analysts learning to build ETL flows visually
- Data-curious business users
- Python developers wanting visual pipelines
- Educators teaching data cleaning with pandas
- Contributors extending FlowFrame

**Core Promise:**
> Learn FlowFrame in 5 minutes. Build your first ETL flow in 15 minutes.

---

## Documentation Structure

Actual structure (keep this in sync with the files on disk and with
`.vitepress/config.ts`):

```text
docs/
├── CLAUDE.md                    # This file (docs standards)
├── CI_CD.md                     # CI/CD pipeline notes
├── index.md                     # Homepage
├── faq.md                       # Frequently asked questions
├── guide/                       # User guides
│   ├── getting-started.md       # Intro & concepts
│   ├── installation.md          # Backend + frontend setup
│   ├── quick-start.md           # First 5-minute flow
│   ├── interface.md             # Editor / UI tour
│   ├── projects-and-runs.md     # Projects, dataset versioning, runs
│   ├── engines.md               # polars vs pandas, export, exec mode
│   ├── scheduling.md            # Built-in cron scheduler
│   ├── cli.md                   # flowframe serve/init/info/check
│   ├── design-system.md         # Visual language / tokens
│   └── troubleshooting.md       # Common issues
├── transformations/
│   └── overview.md              # All 28 nodes + config + generated code
├── examples/                    # Real-world, end-to-end walkthroughs
│   ├── sales-analysis.md
│   ├── customer-segmentation.md
│   ├── time-series.md
│   └── data-quality.md
├── api/
│   └── rest-api.md              # REST endpoints
└── .vitepress/
    ├── config.ts
    └── (theme/, public/ as needed)
```

> **Guardrail:** never document a feature that isn't implemented. The backend
> (`backend/app/engine/registry.py`, `backend/app/api/routes/`,
> `backend/app/core/config.py`, `backend/app/cli.py`) and the frontend
> (`frontend/src/features/`) are authoritative — verify against them before adding
> or expanding a page.

---

## Documentation Standards

### Writing Style

1. **Clear & Concise** — explain concepts without jargon
2. **Active Voice** — "you can rename columns" not "columns can be renamed"
3. **Examples First** — show before explaining
4. **Beginner-Friendly** — no assumed knowledge of ETL
5. **Consistent Terminology** — use glossary terms consistently

### Structure

Every page should have:

1. **Brief intro** — what you'll learn (2-3 sentences)
2. **Prerequisites** — what you need to know/have
3. **Step-by-step guide** — with screenshots/GIFs
4. **Examples** — working code/flows
5. **Tips & Gotchas** — common mistakes
6. **Next Steps** — what to learn next

### Code Examples

- **All examples must work** — test before publishing
- **Beginner code** — not optimized, readable
- **Sample data included** — downloadable CSV/Excel files
- **Python code** — show exported code where relevant
- **Interactive preview** — embed flow screenshots/GIFs

### Screenshots & GIFs

- **GIF for animations** — showing interaction
- **PNG for static** — UI details
- **High DPI** — 2x resolution for clarity
- **Annotated** — arrows pointing to key UI elements
- **Alt text** — describe what's happening
- **File size** — optimize (< 1MB per GIF)

### Front Matter

Every markdown file starts with:

```yaml
---
title: Page Title
description: Brief description for search/preview
search: keyword1 keyword2
layout: doc
---
```

### Headings

```markdown
# Page Title (H1 - only one per page)

## Major Section (H2)

### Subsection (H3)

#### Details (H4)
```

### Links

- **Internal:** `[text](./path/to/page)` or `[text](../features/flows.md)`
- **External:** `[text](https://example.com){target=_blank}`
- **Anchors:** `[Jump to section](#section-heading)`

### Callouts

```markdown
:::info
Informational tip
:::

:::tip
Helpful advice
:::

:::warning
Important caution
:::

:::danger
Critical warning
:::

:::details Click to expand
Hidden details content
:::
```

---

## Feature Documentation Template

Every transformation node needs:

```markdown
---
title: [Transformation Name]
description: What this does and when to use it
---

# [Transformation Name]

Brief one-liner: what it does.

## Use Cases

When you would use this:
- Scenario 1
- Scenario 2

## How It Works

Explanation of the transformation logic.

## Configuration

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| param1 | string | Yes | ... |
| param2 | number | No | ... |

## Examples

### Example 1: Basic Usage
[Screenshot/GIF]

Step-by-step instructions.

### Example 2: Advanced Usage
[Screenshot/GIF]

### Generated Python Code

\`\`\`python
# What FlowFrame exports
df_output = df.drop(columns=['col1', 'col2'])
\`\`\`

## Tips & Common Mistakes

- **Tip:** ...
- **Mistake:** Don't ...
- **Edge case:** When there are ...

## See Also

- [Related transformation](./related.md)
- [Example: Data cleaning](../examples/data-quality.md)
```

---

## VitePress Configuration

### Build & Deployment

- **Build:** `npm run docs:build` → generates static HTML
- **Preview:** `npm run docs:preview` → test locally
- **Deploy:** GitHub Pages (automatic via workflow)

### Theme Customization

- **Colors:** `docs/.vitepress/theme/styles/variables.css`
- **Components:** `docs/.vitepress/theme/components/`
- **Layout:** `docs/.vitepress/theme/layout.vue`

### Search

- Full-text search included with VitePress
- Indexed at build time
- No external service needed

---

## Documentation Development

### Local Setup

```bash
cd docs
npm install
npm run dev          # Start dev server (port 5173)
npm run build        # Build for production
npm run preview      # Preview built site
npm run search:build # Rebuild search index
```

### Adding a New Page

1. Create `.md` file in appropriate folder
2. Add front matter with title/description
3. Add navigation entry in `.vitepress/config.ts`
4. Run `npm run dev` to preview
5. Commit & push — GitHub Actions rebuilds

### Markdown Features

- **Syntax highlighting** — code blocks with language
- **Line numbers** — `{lineNumbers}` in code blocks
- **Line highlighting** — `{4-6}` in code blocks
- **Tabs** — show multiple code examples
- **Tables** — markdown tables
- **Footnotes** — reference links
- **Emoji** — `:smile:` syntax

### Updating Examples

1. Create sample data (CSV, Excel, Parquet)
2. Build the flow in FlowFrame
3. Take screenshot/GIF
4. Export Python code
5. Add to documentation
6. Version control sample files in `docs/public/samples/`

---

## Publishing & Deployment

### GitHub Pages Workflow

1. Push docs changes to `main`
2. GitHub Actions triggers `docs-deploy.yml`
3. Builds site with `npm run build`
4. Deploys to `gh-pages` branch
5. Published at `https://rodrigo-arenas.github.io/FlowFrame`

### Manual Build & Deploy

```bash
cd docs
npm run build
# Deploy the `docs/.vitepress/dist/` folder to gh-pages
```

---

## SEO & Analytics

### Search Engine Optimization

- **Meta descriptions** — every page
- **Semantic HTML** — VitePress handles
- **Internal links** — link related pages
- **Headings** — logical hierarchy
- **Alt text** — all images described

### Analytics (Optional)

Can add Google Analytics or Plausible:

```ts
// .vitepress/config.ts
export default {
  head: [
    ['script', { async: '', src: 'https://...' }]
  ]
}
```

---

## Maintenance

### Keeping Docs Fresh

- Update docs with every feature release
- Review quarterly for accuracy
- Fix broken links in CI
- Update examples when UI changes
- Archive old docs on major version

### Review Process

Before publishing:

1. Technical review — accuracy
2. UX review — clarity & structure
3. Copy edit — grammar & tone
4. Link check — no 404s
5. Screenshot check — current UI

---

## Tools & Dependencies

### Core

- **VitePress** — static site generator
- **Vue 3** — for interactive components (if needed)
- **TypeScript** — config files

### Build & Optimization

- **@vitejs/plugin-vue** — Vue support
- **vite** — bundler

### Search (Optional)

- **@vitepress-plugin/search** — local search

### Sample Data

- **faker.js** — generate test data

---

## Future Features

- [ ] Dark mode toggle
- [ ] Version selector
- [ ] Interactive flow builder (embed)
- [ ] Video tutorials
- [ ] Community contributions section
- [ ] Internationalization (i18n)
- [ ] Multi-language support
- [ ] Offline documentation (download)

---

## References

- [VitePress Docs](https://vitepress.dev/)
- [GitHub Pages Guide](https://pages.github.com/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Vue 3 Docs](https://vuejs.org/)

---

**Last Updated:** 2026-06-22
