import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'FlowFrame',
  description: 'Visual ETL builder for pandas — Simple, local-first data pipelines',
  lang: 'en-US',

  head: [
    ['meta', { name: 'theme-color', content: '#3c3c3d' }],
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
        text: 'Features',
        link: '/features/datasets',
        activeMatch: '/features/',
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
            { text: 'Quick Start (5 min)', link: '/guide/quick-start' },
            { text: 'Interface Tour', link: '/guide/interface' },
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

      '/features/': [
        {
          text: 'Core Features',
          items: [
            { text: 'Datasets', link: '/features/datasets' },
            { text: 'Flows', link: '/features/flows' },
            { text: 'Live Preview', link: '/features/preview' },
            { text: 'Code Export', link: '/features/export' },
            { text: 'Runs & History', link: '/features/runs' },
          ],
        },
      ],

      '/transformations/': [
        {
          text: 'Reference',
          items: [{ text: 'All Transformations', link: '/transformations/overview' }],
        },
        {
          text: 'Cleaning',
          items: [
            { text: 'Drop Columns', link: '/transformations/cleaning/drop-columns' },
            { text: 'Rename Columns', link: '/transformations/cleaning/rename-columns' },
            { text: 'Filter Rows', link: '/transformations/cleaning/filter-rows' },
            { text: 'Drop Nulls', link: '/transformations/cleaning/drop-nulls' },
            { text: 'Fill Nulls', link: '/transformations/cleaning/fill-nulls' },
            { text: 'Remove Duplicates', link: '/transformations/cleaning/remove-duplicates' },
            { text: 'Change Data Types', link: '/transformations/cleaning/change-types' },
            { text: 'Sort', link: '/transformations/cleaning/sort' },
          ],
        },
        {
          text: 'Transform',
          items: [
            { text: 'Select Columns', link: '/transformations/transform/select-columns' },
            { text: 'Calculated Column', link: '/transformations/transform/calculated-column' },
            { text: 'Group & Aggregate', link: '/transformations/transform/group-aggregate' },
            { text: 'Join', link: '/transformations/transform/join' },
            { text: 'Union', link: '/transformations/transform/union' },
          ],
        },
        {
          text: 'Input/Output',
          items: [
            { text: 'CSV Input', link: '/transformations/io/csv-input' },
            { text: 'Excel Input', link: '/transformations/io/excel-input' },
            { text: 'Parquet Input', link: '/transformations/io/parquet-input' },
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
            { text: 'REST API', link: '/api/rest-api' },
            { text: 'Error Codes', link: '/api/errors' },
          ],
        },
      ],

      '/advanced/': [
        {
          text: 'Advanced Topics',
          items: [
            { text: 'Custom Nodes', link: '/advanced/custom-nodes' },
            { text: 'Deployment', link: '/advanced/deployment' },
            { text: 'Performance', link: '/advanced/performance' },
            { text: 'Architecture', link: '/advanced/architecture' },
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
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 Rodrigo Arenas',
    },
  },
})
