<script setup lang="ts">
interface PipelineNode {
  type: 'input' | 'clean' | 'transform' | 'output' | 'ml'
  label: string
  detail?: string
}

withDefaults(defineProps<{
  nodes: PipelineNode[]
  vertical?: boolean
}>(), {
  vertical: false,
})

const icons: Record<string, string> = {
  input: '📥',
  clean: '🧹',
  transform: '⚡',
  output: '📤',
  ml: '🤖',
}

function iconFor(type: string): string {
  return icons[type] ?? '⚙️'
}
</script>

<template>
  <div class="flow-pipeline" :class="{ 'flow-pipeline--vertical': vertical }">
    <template v-for="(node, i) in nodes" :key="i">
      <div class="pipeline-node" :class="`pipeline-node--${node.type}`">
        <span class="pipeline-node__icon" aria-hidden="true">{{ iconFor(node.type) }}</span>
        <div class="pipeline-node__body">
          <div class="pipeline-node__label">{{ node.label }}</div>
          <div v-if="node.detail" class="pipeline-node__detail">{{ node.detail }}</div>
        </div>
        <span class="pipeline-node__badge">{{ node.type }}</span>
      </div>
      <div v-if="i < nodes.length - 1" class="pipeline-arrow" aria-hidden="true">
        <svg v-if="!vertical" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 5v14"/><path d="m5 12 7 7 7-7"/>
        </svg>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ── Container ────────────────────────────────────────── */
.flow-pipeline {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin: 24px 0;
  padding: 20px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  overflow-x: auto;
}

.flow-pipeline--vertical {
  flex-direction: column;
  align-items: flex-start;
}

/* ── Node card ────────────────────────────────────────── */
.pipeline-node {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border-radius: 8px;
  border-left: 4px solid transparent;
  background: var(--vp-c-bg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  min-width: 160px;
  position: relative;
}

/* category colours */
.pipeline-node--input  { border-left-color: #059669; }
.pipeline-node--clean  { border-left-color: #0284c7; }
.pipeline-node--transform { border-left-color: #7c3aed; }
.pipeline-node--output { border-left-color: #d97706; }
.pipeline-node--ml     { border-left-color: #4338ca; }

.pipeline-node--input  .pipeline-node__icon { color: #059669; }
.pipeline-node--clean  .pipeline-node__icon { color: #0284c7; }
.pipeline-node--transform .pipeline-node__icon { color: #7c3aed; }
.pipeline-node--output .pipeline-node__icon { color: #d97706; }
.pipeline-node--ml     .pipeline-node__icon { color: #4338ca; }

.pipeline-node--input  .pipeline-node__badge { background: rgba(5,150,105,0.12);  color: #059669; }
.pipeline-node--clean  .pipeline-node__badge { background: rgba(2,132,199,0.12);  color: #0284c7; }
.pipeline-node--transform .pipeline-node__badge { background: rgba(124,58,237,0.12); color: #7c3aed; }
.pipeline-node--output .pipeline-node__badge { background: rgba(217,119,6,0.12);  color: #d97706; }
.pipeline-node--ml     .pipeline-node__badge { background: rgba(67,56,202,0.12);  color: #4338ca; }

/* ── Node internals ───────────────────────────────────── */
.pipeline-node__icon {
  font-size: 17px;
  flex-shrink: 0;
  line-height: 1;
}

.pipeline-node__body {
  flex: 1;
  min-width: 0;
}

.pipeline-node__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pipeline-node__detail {
  font-size: 11px;
  color: var(--vp-c-text-2);
  margin-top: 2px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pipeline-node__badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* ── Arrow connector ──────────────────────────────────── */
.pipeline-arrow {
  color: var(--vp-c-text-3);
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* ── Responsive: force vertical on small screens ─────── */
@media (max-width: 640px) {
  .flow-pipeline {
    flex-direction: column;
    align-items: flex-start;
  }
  .pipeline-arrow svg {
    transform: rotate(90deg);
  }
}
</style>
