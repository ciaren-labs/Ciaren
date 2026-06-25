<script setup lang="ts">
const LB = '{{'
const RB = '}}'

interface Param {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean'
  default?: string
  description?: string
}

interface Override {
  source: 'run' | 'schedule' | 'default'
  label: string
  value: string
}

withDefaults(defineProps<{
  params: Param[]
  overrides?: Override[]
  nodeExample?: { label: string; field: string; ref: string }
}>(), {
  overrides: () => [],
})

const typeColor: Record<string, string> = {
  string: '#0284c7',
  integer: '#059669',
  number: '#059669',
  boolean: '#7c3aed',
}

const sourceIcon: Record<string, string> = {
  run: '▶',
  schedule: '⏰',
  default: '📋',
}

const sourceColor: Record<string, string> = {
  run: '#7c3aed',
  schedule: '#d97706',
  default: '#6b7280',
}
</script>

<template>
  <div class="pf-wrapper">
    <!-- Row: declare → reference → resolve -->
    <div class="pf-flow">

      <!-- 1. Declare -->
      <div class="pf-card pf-card--declare">
        <div class="pf-card-label">① Declare on the flow</div>
        <div class="pf-params">
          <div v-for="p in params" :key="p.name" class="pf-param">
            <span class="pf-param-name">{{ p.name }}</span>
            <span class="pf-param-type" :style="{ color: typeColor[p.type] }">{{ p.type }}</span>
            <span v-if="p.default !== undefined" class="pf-param-default">= {{ p.default }}</span>
            <span v-else class="pf-param-required">required</span>
            <div v-if="p.description" class="pf-param-desc">{{ p.description }}</div>
          </div>
        </div>
      </div>

      <div class="pf-arrow">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      </div>

      <!-- 2. Reference in node -->
      <div class="pf-card pf-card--node">
        <div class="pf-card-label">② Reference in node config</div>
        <div v-if="nodeExample" class="pf-node-example">
          <div class="pf-node-name">{{ nodeExample.label }}</div>
          <div class="pf-node-row">
            <span class="pf-node-field">{{ nodeExample.field }}</span>
            <span class="pf-node-ref">{{ LB }} {{ nodeExample.ref }} {{ RB }}</span>
          </div>
        </div>
        <div v-else class="pf-node-example">
          <div class="pf-node-name">Any node config field</div>
          <div class="pf-node-row">
            <span class="pf-node-field">value</span>
            <span class="pf-node-ref">{{ LB }} {{ params[0]?.name ?? 'param_name' }} {{ RB }}</span>
          </div>
        </div>
      </div>

      <div class="pf-arrow">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      </div>

      <!-- 3. Resolve at run time -->
      <div class="pf-card pf-card--resolve">
        <div class="pf-card-label">③ Resolved at run time</div>
        <div class="pf-overrides">
          <div
            v-for="(o, i) in overrides.length ? overrides : [
              { source: 'run',      label: 'Per-run override',      value: 'highest priority' },
              { source: 'schedule', label: 'Per-schedule override', value: 'if no run value' },
              { source: 'default',  label: 'Declared default',      value: 'fallback' },
            ]"
            :key="i"
            class="pf-override"
            :style="{ '--src-color': sourceColor[o.source] }"
          >
            <span class="pf-override-icon">{{ sourceIcon[o.source] }}</span>
            <span class="pf-override-label">{{ o.label }}</span>
            <span class="pf-override-value">{{ o.value }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Container ───────────────────────────────────────── */
.pf-wrapper {
  margin: 24px 0;
}

.pf-flow {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
}

/* ── Arrow ───────────────────────────────────────────── */
.pf-arrow {
  color: var(--vp-c-text-3);
  margin-top: 36px;
  flex-shrink: 0;
}

/* ── Card base ───────────────────────────────────────── */
.pf-card {
  flex: 1;
  min-width: 180px;
  border: 1px solid var(--vp-c-border);
  border-top: 3px solid transparent;
  border-radius: 8px;
  background: var(--vp-c-bg);
  overflow: hidden;
}

.pf-card--declare  { border-top-color: #7c3aed; }
.pf-card--node     { border-top-color: #0284c7; }
.pf-card--resolve  { border-top-color: #059669; }

.pf-card-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-2);
  padding: 7px 12px;
  background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-border-light);
}

/* ── Params list ─────────────────────────────────────── */
.pf-params {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pf-param {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  font-size: 12px;
}

.pf-param-name {
  font-weight: 700;
  font-family: var(--vp-font-family-mono);
  color: var(--vp-c-text-1);
}

.pf-param-type {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--vp-c-bg-mute);
}

.pf-param-default {
  font-family: var(--vp-font-family-mono);
  font-size: 11px;
  color: var(--vp-c-text-2);
}

.pf-param-required {
  font-size: 10px;
  font-weight: 700;
  color: #dc2626;
  background: rgba(220,38,38,0.08);
  padding: 1px 5px;
  border-radius: 3px;
}

.pf-param-desc {
  width: 100%;
  font-size: 11px;
  color: var(--vp-c-text-3);
  margin-top: 1px;
  font-style: italic;
}

/* ── Node example ────────────────────────────────────── */
.pf-node-example {
  padding: 10px 12px;
}

.pf-node-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 8px;
}

.pf-node-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  padding: 5px 8px;
  background: var(--vp-c-bg-mute);
  border-radius: 5px;
  gap: 8px;
}

.pf-node-field {
  color: var(--vp-c-text-2);
}

.pf-node-ref {
  font-family: var(--vp-font-family-mono);
  font-size: 11px;
  font-weight: 700;
  color: #7c3aed;
  background: rgba(124,58,237,0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

/* ── Override list ───────────────────────────────────── */
.pf-overrides {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pf-override {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  padding: 5px 8px;
  border-left: 3px solid var(--src-color, #6b7280);
  background: var(--vp-c-bg-mute);
  border-radius: 0 5px 5px 0;
}

.pf-override-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.pf-override-label {
  flex: 1;
  color: var(--vp-c-text-1);
  font-weight: 500;
}

.pf-override-value {
  font-size: 10px;
  color: var(--vp-c-text-3);
  white-space: nowrap;
}

/* ── Responsive ──────────────────────────────────────── */
@media (max-width: 680px) {
  .pf-flow {
    flex-direction: column;
    align-items: stretch;
  }
  .pf-arrow {
    margin-top: 0;
    transform: rotate(90deg);
    align-self: center;
  }
}
</style>
