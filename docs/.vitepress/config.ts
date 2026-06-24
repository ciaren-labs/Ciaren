import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'FlowFrame',
  description: 'Visual ETL builder — Simple, local-first data pipelines on polars or pandas',
  lang: 'en-US',

  head: [
    ['meta', { name: 'theme-color', content: '#7c3aed' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:locale', content: 'en' }],
  ],

  lastUpdated: true,
  cleanUrls: true,

  ignoreDeadLinks: true,

  markdown: {
    lineNumbers: true,
    math: false,
  },

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'FlowFrame',

    nav: [
      {
        text: 'Guide',
        link: '/guide/getting-started',
        activeMatch: '/guide/',
      },
      {
        text: 'Transformations',
        link: '/transformations/overview',
        activeMatch: '/transformations/',
      },
      {
        text: 'Examples',
        link: '/examples/sales-analysis',
        activeMatch: '/examples/',
      },
      {
        text: 'API',
        link: '/api/rest-api',
        activeMatch: '/api/',
      },
      {
        text: 'FAQ',
        link: '/faq',
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/getting-started' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Advanced Setup', link: '/guide/advanced-setup' },
            { text: 'Quick Start (5 min)', link: '/guide/quick-start' },
            { text: 'Demo Project & Tutorials', link: '/guide/demo-project' },
            { text: 'Interface Tour', link: '/guide/interface' },
          ],
        },
        {
          text: 'Features',
          items: [
            { text: 'Projects & Runs', link: '/guide/projects-and-runs' },
            { text: 'Database Connections', link: '/guide/connections' },
            { text: 'Machine Learning', link: '/guide/ml-quickstart' },
            { text: 'Visualizations', link: '/guide/visualizations' },
            { text: 'Engines (polars / pandas)', link: '/guide/engines' },
            { text: 'Scheduling', link: '/guide/scheduling' },
            { text: 'CLI Reference', link: '/guide/cli' },
          ],
        },
        {
          text: 'Deployment',
          items: [
            { text: 'Docker', link: '/guide/docker' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'Design System', link: '/guide/design-system' },
          ],
        },
        {
          text: 'Help',
          items: [
            { text: 'Troubleshooting', link: '/guide/troubleshooting' },
            { text: 'FAQ', link: '/faq' },
          ],
        },
      ],

      '/transformations/': [
        {
          text: 'Reference',
          items: [{ text: 'All Transformations', link: '/transformations/overview' }],
        },
        {
          text: 'Input & Output',
          items: [
            { text: 'File input (CSV/Excel/Parquet)', link: '/transformations/file-input' },
            { text: 'File output (CSV/Excel/Parquet)', link: '/transformations/file-output' },
            { text: 'SQL input', link: '/transformations/sql-input' },
            { text: 'SQL output', link: '/transformations/sql-output' },
          ],
        },
        {
          text: 'Columns',
          items: [
            { text: 'Drop columns', link: '/transformations/drop-columns' },
            { text: 'Rename columns', link: '/transformations/rename-columns' },
            { text: 'Select columns', link: '/transformations/select-columns' },
            { text: 'Cast types', link: '/transformations/cast-types' },
          ],
        },
        {
          text: 'Nulls',
          items: [
            { text: 'Drop nulls', link: '/transformations/drop-nulls' },
            { text: 'Fill nulls', link: '/transformations/fill-nulls' },
          ],
        },
        {
          text: 'Rows',
          items: [
            { text: 'Filter rows', link: '/transformations/filter-rows' },
            { text: 'Sort rows', link: '/transformations/sort-rows' },
            { text: 'Limit rows', link: '/transformations/limit-rows' },
            { text: 'Sample rows', link: '/transformations/sample-rows' },
            { text: 'Remove duplicates', link: '/transformations/remove-duplicates' },
          ],
        },
        {
          text: 'Text',
          items: [
            { text: 'Replace values', link: '/transformations/replace-values' },
            { text: 'String transform', link: '/transformations/string-transform' },
            { text: 'Split column', link: '/transformations/split-column' },
            { text: 'Map values', link: '/transformations/map-values' },
          ],
        },
        {
          text: 'Numeric',
          items: [
            { text: 'Round numbers', link: '/transformations/round-numbers' },
            { text: 'Remove outliers', link: '/transformations/remove-outliers' },
            { text: 'Bin column', link: '/transformations/bin-column' },
          ],
        },
        {
          text: 'Reshape & combine',
          items: [
            { text: 'Calculated column', link: '/transformations/calculated-column' },
            { text: 'Group by + aggregate', link: '/transformations/group-by-aggregate' },
            { text: 'Join', link: '/transformations/join' },
            { text: 'Union / Concat', link: '/transformations/union-concat' },
            { text: 'Pivot', link: '/transformations/pivot' },
            { text: 'Unpivot', link: '/transformations/unpivot' },
            { text: 'Extract date parts', link: '/transformations/extract-date-parts' },
            { text: 'Parse dates', link: '/transformations/parse-dates' },
          ],
        },
        {
          text: 'Analytics',
          items: [
            { text: 'Window function', link: '/transformations/window-function' },
            { text: 'Conditional column', link: '/transformations/conditional-column' },
          ],
        },
        {
          text: 'Machine Learning',
          items: [
            { text: 'ML nodes', link: '/transformations/machine-learning' },
          ],
        },
      ],

      '/examples/': [
        {
          text: 'Real-World Examples',
          items: [
            { text: 'Sales Analysis', link: '/examples/sales-analysis' },
            { text: 'Customer Segmentation', link: '/examples/customer-segmentation' },
            { text: 'Time Series', link: '/examples/time-series' },
            { text: 'Data Quality Checks', link: '/examples/data-quality' },
          ],
        },
      ],

      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/rest-api' },
          ],
        },
        {
          text: 'Resources',
          items: [
            { text: 'Projects', link: '/api/projects' },
            { text: 'Datasets', link: '/api/datasets' },
            { text: 'Flows', link: '/api/flows' },
            { text: 'Runs', link: '/api/runs' },
            { text: 'Transformations', link: '/api/transformations' },
            { text: 'Schedules', link: '/api/schedules' },
            { text: 'Connections', link: '/api/connections' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/rodrigo-arenas/FlowFrame' },
    ],

    search: {
      provider: 'local',
    },

    editLink: {
      pattern: 'https://github.com/rodrigo-arenas/FlowFrame/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message:
        'Released under the Apache License 2.0. Created by ' +
        '<a href="https://www.rodrigo-arenas.com/" target="_blank" rel="noreferrer">Rodrigo Arenas</a> ' +
        '(<a href="https://github.com/rodrigo-arenas" target="_blank" rel="noreferrer">GitHub</a>).',
      copyright:
        'Copyright © 2026 <a href="https://www.rodrigo-arenas.com/" target="_blank" rel="noreferrer">Rodrigo Arenas</a>',
    },
  },
})
