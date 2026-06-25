<script setup lang="ts">
interface NodeEntry {
  label: string
  link: string
}

interface Category {
  name: string
  color: string
  bg: string
  icon: string
  nodes: NodeEntry[]
}

const categories: Category[] = [
  {
    name: 'Input',
    color: '#059669',
    bg: 'rgba(5,150,105,0.09)',
    icon: '📥',
    nodes: [
      { label: 'File (CSV / Excel / Parquet)', link: '/transformations/file-input' },
      { label: 'SQL Input', link: '/transformations/sql-input' },
      { label: 'Storage (S3 / GCS / Azure)', link: '/transformations/storage-input' },
    ],
  },
  {
    name: 'Columns',
    color: '#0284c7',
    bg: 'rgba(2,132,199,0.09)',
    icon: '🏷️',
    nodes: [
      { label: 'Drop Columns', link: '/transformations/drop-columns' },
      { label: 'Rename Columns', link: '/transformations/rename-columns' },
      { label: 'Select Columns', link: '/transformations/select-columns' },
      { label: 'Cast Types', link: '/transformations/cast-types' },
    ],
  },
  {
    name: 'Nulls',
    color: '#0284c7',
    bg: 'rgba(2,132,199,0.09)',
    icon: '🕳️',
    nodes: [
      { label: 'Drop Nulls', link: '/transformations/drop-nulls' },
      { label: 'Fill Nulls', link: '/transformations/fill-nulls' },
    ],
  },
  {
    name: 'Rows',
    color: '#0284c7',
    bg: 'rgba(2,132,199,0.09)',
    icon: '🔍',
    nodes: [
      { label: 'Filter Rows', link: '/transformations/filter-rows' },
      { label: 'Sort Rows', link: '/transformations/sort-rows' },
      { label: 'Limit Rows', link: '/transformations/limit-rows' },
      { label: 'Sample Rows', link: '/transformations/sample-rows' },
      { label: 'Remove Duplicates', link: '/transformations/remove-duplicates' },
    ],
  },
  {
    name: 'Text',
    color: '#0284c7',
    bg: 'rgba(2,132,199,0.09)',
    icon: '📝',
    nodes: [
      { label: 'Replace Values', link: '/transformations/replace-values' },
      { label: 'String Transform', link: '/transformations/string-transform' },
      { label: 'Split Column', link: '/transformations/split-column' },
      { label: 'Map Values', link: '/transformations/map-values' },
    ],
  },
  {
    name: 'Numeric',
    color: '#0284c7',
    bg: 'rgba(2,132,199,0.09)',
    icon: '🔢',
    nodes: [
      { label: 'Round Numbers', link: '/transformations/round-numbers' },
      { label: 'Remove Outliers', link: '/transformations/remove-outliers' },
      { label: 'Bin Column', link: '/transformations/bin-column' },
    ],
  },
  {
    name: 'Reshape & Combine',
    color: '#7c3aed',
    bg: 'rgba(124,58,237,0.09)',
    icon: '⚡',
    nodes: [
      { label: 'Calculated Column', link: '/transformations/calculated-column' },
      { label: 'Group By + Aggregate', link: '/transformations/group-by-aggregate' },
      { label: 'Join', link: '/transformations/join' },
      { label: 'Union / Concat', link: '/transformations/union-concat' },
      { label: 'Pivot', link: '/transformations/pivot' },
      { label: 'Unpivot', link: '/transformations/unpivot' },
      { label: 'Extract Date Parts', link: '/transformations/extract-date-parts' },
      { label: 'Parse Dates', link: '/transformations/parse-dates' },
    ],
  },
  {
    name: 'Analytics',
    color: '#7c3aed',
    bg: 'rgba(124,58,237,0.09)',
    icon: '📊',
    nodes: [
      { label: 'Window Function', link: '/transformations/window-function' },
      { label: 'Conditional Column', link: '/transformations/conditional-column' },
    ],
  },
  {
    name: 'Machine Learning',
    color: '#4338ca',
    bg: 'rgba(67,56,202,0.09)',
    icon: '🤖',
    nodes: [
      { label: 'ML Nodes (Train / Predict / Evaluate)', link: '/transformations/machine-learning' },
    ],
  },
  {
    name: 'Output',
    color: '#d97706',
    bg: 'rgba(217,119,6,0.09)',
    icon: '📤',
    nodes: [
      { label: 'File (CSV / Excel / Parquet)', link: '/transformations/file-output' },
      { label: 'SQL Output', link: '/transformations/sql-output' },
      { label: 'Storage (S3 / GCS / Azure)', link: '/transformations/storage-output' },
    ],
  },
]
</script>

<template>
  <div class="ncg-grid">
    <div
      v-for="cat in categories"
      :key="cat.name"
      class="ncg-card"
      :style="{ '--cat-color': cat.color, '--cat-bg': cat.bg }"
    >
      <div class="ncg-header">
        <span class="ncg-icon" aria-hidden="true">{{ cat.icon }}</span>
        <span class="ncg-title">{{ cat.name }}</span>
      </div>
      <ul class="ncg-nodes">
        <li v-for="node in cat.nodes" :key="node.label">
          <a :href="node.link">{{ node.label }}</a>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.ncg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
  margin: 28px 0;
}

.ncg-card {
  border: 1px solid var(--vp-c-border);
  border-top: 3px solid var(--cat-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--vp-c-bg);
  transition: box-shadow 0.12s ease, transform 0.12s ease;
}

.ncg-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.dark .ncg-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
}

.ncg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--cat-bg);
  border-bottom: 1px solid var(--vp-c-border-light);
}

.ncg-icon {
  font-size: 16px;
  line-height: 1;
}

.ncg-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--cat-color);
}

.ncg-nodes {
  list-style: none;
  margin: 0;
  padding: 10px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ncg-nodes li {
  margin: 0;
  padding: 0;
}

.ncg-nodes a {
  font-size: 13px;
  color: var(--vp-c-text-1);
  text-decoration: none;
  display: block;
  padding: 2px 0;
  transition: color 0.1s;
}

.ncg-nodes a:hover {
  color: var(--cat-color);
}
</style>
