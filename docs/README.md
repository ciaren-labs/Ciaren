# FlowFrame Documentation

User-facing documentation for FlowFrame — built with VitePress and deployed to GitHub Pages.

## Quick Start

### Local Development

```bash
npm install
npm run dev
```

Visit `http://localhost:5173`

### Build

```bash
npm run build
```

Output is in `.vitepress/dist/`

### Lint Markdown

```bash
npm run lint
```

## Structure

```
├── index.md                           # Homepage
├── guide/
│   ├── getting-started.md
│   ├── installation.md
│   ├── quick-start.md
│   ├── interface.md
│   └── troubleshooting.md
├── features/
│   ├── datasets.md
│   ├── flows.md
│   ├── preview.md
│   ├── export.md
│   └── runs.md
├── transformations/
│   ├── overview.md
│   ├── cleaning/
│   ├── transform/
│   └── io/
├── examples/
│   ├── sales-analysis.md
│   ├── customer-segmentation.md
│   ├── time-series.md
│   └── data-quality.md
├── api/
│   ├── rest-api.md
│   ├── authentication.md
│   └── errors.md
├── advanced/
│   ├── custom-nodes.md
│   ├── deployment.md
│   ├── performance.md
│   └── architecture.md
├── faq.md
├── roadmap.md
└── .vitepress/
    ├── config.ts              # VitePress configuration
    ├── theme/
    │   ├── index.ts
    │   └── styles/
    │       ├── variables.css
    │       └── custom.css
    └── public/                # Static assets
        ├── logo.svg
        └── images/
```

## Writing Documentation

See [CLAUDE.md](./CLAUDE.md) for detailed documentation standards.

### Front Matter

Every page needs:

```yaml
---
title: Page Title
description: Brief description for search
search: keyword1 keyword2
---
```

### Navigation

Update `.vitepress/config.ts` to add pages to the sidebar.

### Code Examples

```markdown
:::info
Informational note
:::

:::warning
Important warning
:::

\`\`\`python
# Python code example
df = df.drop(columns=['col1'])
\`\`\`
```

## Adding Content

### New Page

1. Create `.md` file in appropriate folder
2. Add front matter (title, description)
3. Write content
4. Update `.vitepress/config.ts` sidebar (if needed)
5. Test: `npm run dev`

### New Transformation

Create file in `transformations/{cleaning|transform|io}/`:

```markdown
---
title: Transformation Name
description: What it does
---

# [Transformation Name]

## Use Cases

## How It Works

## Configuration

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|

## Examples

## Tips

## See Also
```

### New Example

Create file in `examples/`:

```markdown
---
title: Example Name
description: What this example shows
---

# [Example Name]

## Overview

## Step-by-Step

## Download Sample Data

## Generated Python Code

\`\`\`python
# Exported code here
\`\`\`
```

## Deployment

Automatic via `.github/workflows/docs-deploy.yml`:

1. Push to `main` branch
2. GitHub Actions builds docs
3. Deployed to GitHub Pages
4. Available at `https://rodrigo-arenas.github.io/FlowFrame`

### Manual Deployment

```bash
npm run build

# Deploy .vitepress/dist to gh-pages branch
git add .vitepress/dist
git commit -m "Deploy docs"
git push origin gh-pages
```

## Assets

Store images and files in `.vitepress/public/`:

```
.vitepress/
├── public/
│   ├── logo.svg
│   ├── images/
│   │   ├── feature-preview.png
│   │   ├── ui-tour.gif
│   │   └── ...
│   └── samples/
│       ├── sales.csv
│       ├── customers.xlsx
│       └── ...
```

Reference in markdown:

```markdown
![Alt text](/images/feature-preview.png)
[Download sample](samples/sales.csv)
```

## Search

VitePress includes local search. No external service needed.

Search is built at build time from page titles, descriptions, and content.

## Style Guide

- **Tone:** Friendly, clear, beginner-friendly
- **Active voice:** "You can rename columns" not "Columns can be renamed"
- **Examples first:** Show before explaining
- **Avoid jargon:** Explain technical terms
- **Links:** Link related pages

## Performance

- No external fonts (uses system fonts)
- Syntax highlighting at build time
- No JavaScript animations
- ~40KB gzipped total

## Questions?

See [CLAUDE.md](./CLAUDE.md) for complete documentation standards.

---

**Last Updated:** 2026-06-21
