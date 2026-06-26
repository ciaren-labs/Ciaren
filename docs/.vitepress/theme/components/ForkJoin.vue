<script setup lang="ts">
interface PipelineNode {
  type: 'input' | 'clean' | 'transform' | 'output' | 'ml'
  label: string
  detail?: string
}

withDefaults(defineProps<{
  left: PipelineNode[]
  right: PipelineNode[]
  join: { label: string; detail?: string }
  after?: PipelineNode[]
}>(), {
  after: () => [],
})

const icons: Record<string, string> = {
  input: '📥', clean: '🧹', transform: '⚡', output: '📤', ml: '🤖',
}
function icon(type: string) { return icons[type] ?? '⚙️' }
</script>

<template>
  <div class="fj-wrapper">
    <!-- Left + right branches side by side -->
    <div class="fj-branches">
      <!-- Left branch -->
      <div class="fj-branch">
        <div class="fj-branch-label">Left input</div>
        <div class="fj-nodes">
          <template v-for="(node, i) in left" :key="i">
            <div class="fj-node" :class="`fj-node--${node.type}`">
              <span class="fj-node__icon">{{ icon(node.type) }}</span>
              <div class="fj-node__body">
                <div class="fj-node__label">{{ node.label }}</div>
                <div v-if="node.detail" class="fj-node__detail">{{ node.detail }}</div>
              </div>
            </div>
            <div v-if="i < left.length - 1" class="fj-arrow-h">→</div>
          </template>
        </div>
      </div>

      <!-- Merge lines + Join node -->
      <div class="fj-merge">
        <div class="fj-merge-lines">
          <div class="fj-merge-line fj-merge-line--top"></div>
          <div class="fj-merge-line fj-merge-line--bot"></div>
        </div>
        <div class="fj-join-node">
          <span class="fj-node__icon">🔗</span>
          <div class="fj-node__body">
            <div class="fj-node__label">{{ join.label }}</div>
            <div v-if="join.detail" class="fj-node__detail">{{ join.detail }}</div>
          </div>
        </div>
      </div>

      <!-- Right branch -->
      <div class="fj-branch fj-branch--right">
        <div class="fj-branch-label">Right input</div>
        <div class="fj-nodes">
          <template v-for="(node, i) in right" :key="i">
            <div class="fj-node" :class="`fj-node--${node.type}`">
              <span class="fj-node__icon">{{ icon(node.type) }}</span>
              <div class="fj-node__body">
                <div class="fj-node__label">{{ node.label }}</div>
                <div v-if="node.detail" class="fj-node__detail">{{ node.detail }}</div>
              </div>
            </div>
            <div v-if="i < right.length - 1" class="fj-arrow-h">→</div>
          </template>
        </div>
      </div>
    </div>

    <!-- After-join nodes -->
    <div v-if="after && after.length" class="fj-after">
      <div class="fj-arrow-h fj-arrow-h--lg">→</div>
      <template v-for="(node, i) in after" :key="i">
        <div class="fj-node" :class="`fj-node--${node.type}`">
          <span class="fj-node__icon">{{ icon(node.type) }}</span>
          <div class="fj-node__body">
            <div class="fj-node__label">{{ node.label }}</div>
            <div v-if="node.detail" class="fj-node__detail">{{ node.detail }}</div>
          </div>
        </div>
        <div v-if="i < after.length - 1" class="fj-arrow-h">→</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* ── Outer container ───────────────────────────────────── */
.fj-wrapper {
  margin: 24px 0;
  padding: 20px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-x: auto;
}

/* ── Branches row ──────────────────────────────────────── */
.fj-branches {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 0;
  align-items: center;
}

.fj-branch {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fj-branch--right {
  align-items: flex-end;
}

.fj-branch-label {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-3);
  margin-bottom: 2px;
}

.fj-branch--right .fj-branch-label {
  text-align: right;
}

.fj-nodes {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

/* ── Merge lines + join ────────────────────────────────── */
.fj-merge {
  display: flex;
  align-items: center;
  gap: 0;
  position: relative;
}

.fj-merge-lines {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 28px;
  position: relative;
  height: 60px;
  flex-shrink: 0;
}

.fj-merge-line {
  position: absolute;
  right: 0;
  width: 20px;
  height: 1px;
  background: var(--vp-c-text-3);
}
.fj-merge-line--top { top: 22%; }
.fj-merge-line--bot { bottom: 22%; }

.fj-merge-lines::after {
  content: '';
  position: absolute;
  right: 0;
  top: 22%;
  bottom: 22%;
  width: 1px;
  background: var(--vp-c-text-3);
}

.fj-join-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  border-radius: 8px;
  border: 2px solid #7c3aed;
  background: var(--vp-c-bg);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  min-width: 120px;
}

/* ── Individual nodes ──────────────────────────────────── */
.fj-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 7px;
  border-left: 3px solid transparent;
  background: var(--vp-c-bg);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  min-width: 0;
}

.fj-node--input    { border-left-color: #059669; }
.fj-node--clean    { border-left-color: #0284c7; }
.fj-node--transform { border-left-color: #7c3aed; }
.fj-node--output   { border-left-color: #d97706; }
.fj-node--ml       { border-left-color: #4338ca; }

.fj-node--input    .fj-node__icon { color: #059669; }
.fj-node--clean    .fj-node__icon { color: #0284c7; }
.fj-node--transform .fj-node__icon { color: #7c3aed; }
.fj-node--output   .fj-node__icon { color: #d97706; }
.fj-node--ml       .fj-node__icon { color: #4338ca; }

.fj-node__icon {
  font-size: 15px;
  flex-shrink: 0;
}

.fj-node__body {
  min-width: 0;
  flex: 1;
}

.fj-node__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  line-height: 1.3;
}

.fj-node__detail {
  font-size: 10px;
  color: var(--vp-c-text-2);
  margin-top: 2px;
  line-height: 1.4;
}

/* ── Arrow ─────────────────────────────────────────────── */
.fj-arrow-h {
  color: var(--vp-c-text-3);
  font-size: 14px;
  flex-shrink: 0;
}

.fj-arrow-h--lg {
  font-size: 18px;
  color: var(--vp-c-text-2);
}

/* ── After row ─────────────────────────────────────────── */
.fj-after {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: 4px;
  border-top: 1px dashed var(--vp-c-border);
}

/* ── Responsive ────────────────────────────────────────── */
@media (max-width: 720px) {
  .fj-branches {
    grid-template-columns: 1fr;
  }
  .fj-merge {
    flex-direction: column;
    align-items: flex-start;
  }
  .fj-merge-lines { display: none; }
  .fj-branch--right { align-items: flex-start; }
  .fj-branch--right .fj-branch-label { text-align: left; }
}
</style>
