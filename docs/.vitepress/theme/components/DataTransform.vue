<script setup lang="ts">
interface TableData {
  columns: string[]
  rows: (string | number | null)[][]
}

withDefaults(defineProps<{
  before: TableData
  after: TableData
  transform?: string
  highlight?: string[]
}>(), {
  transform: 'Transformation',
  highlight: () => [],
})
</script>

<template>
  <div class="dt-wrapper">
    <div class="dt-pane dt-pane--before">
      <div class="dt-pane-label">Before</div>
      <div class="dt-scroll">
        <table class="dt-table">
          <thead>
            <tr>
              <th v-for="col in before.columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in before.rows" :key="ri">
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                :class="{ 'dt-null': cell === null || cell === '' }"
              >
                <span v-if="cell === null || cell === ''">null</span>
                <span v-else>{{ cell }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="dt-meta">{{ before.rows.length }} rows · {{ before.columns.length }} cols</div>
    </div>

    <div class="dt-arrow">
      <div class="dt-arrow-icon">→</div>
      <div class="dt-arrow-label">{{ transform }}</div>
    </div>

    <div class="dt-pane dt-pane--after">
      <div class="dt-pane-label">After</div>
      <div class="dt-scroll">
        <table class="dt-table">
          <thead>
            <tr>
              <th
                v-for="col in after.columns"
                :key="col"
                :class="{ 'dt-col-highlight': highlight.includes(col) }"
              >
                {{ col }}
                <span v-if="highlight.includes(col)" class="dt-new-badge">new</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in after.rows" :key="ri">
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                :class="{
                  'dt-null': cell === null || cell === '',
                  'dt-col-highlight': highlight.includes(after.columns[ci]),
                }"
              >
                <span v-if="cell === null || cell === ''">null</span>
                <span v-else>{{ cell }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="dt-meta">{{ after.rows.length }} rows · {{ after.columns.length }} cols</div>
    </div>
  </div>
</template>

<style scoped>
/* ── Layout ──────────────────────────────────────────── */
.dt-wrapper {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: start;
  margin: 24px 0;
  padding: 20px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
}

@media (max-width: 640px) {
  .dt-wrapper {
    grid-template-columns: 1fr;
  }
  .dt-arrow {
    flex-direction: row !important;
    justify-content: center;
    gap: 8px;
  }
  .dt-arrow-icon {
    transform: rotate(90deg);
  }
}

/* ── Pane ────────────────────────────────────────────── */
.dt-pane {
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  overflow: hidden;
}

.dt-pane--before {
  border-top: 3px solid var(--vp-c-text-3);
}

.dt-pane--after {
  border-top: 3px solid #7c3aed;
}

.dt-pane-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-2);
  padding: 6px 12px;
  background: var(--vp-c-bg-mute);
  border-bottom: 1px solid var(--vp-c-border-light);
}

/* ── Table ───────────────────────────────────────────── */
.dt-scroll {
  overflow-x: auto;
}

.dt-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
  margin: 0;
}

.dt-table th,
.dt-table td {
  border: 1px solid var(--vp-c-border-light);
  padding: 5px 10px;
  text-align: left;
  white-space: nowrap;
}

.dt-table th {
  background: var(--vp-c-bg-soft);
  font-weight: 700;
  font-size: 11px;
  color: var(--vp-c-text-2);
  position: relative;
}

.dt-table tr:hover td {
  background: var(--vp-c-bg-soft);
}

/* null values */
.dt-null {
  color: var(--vp-c-text-3);
  font-style: italic;
  font-size: 11px;
}

/* highlighted new/changed columns */
.dt-col-highlight {
  background: rgba(124, 58, 237, 0.06) !important;
}

.dt-new-badge {
  display: inline-block;
  margin-left: 4px;
  font-size: 8px;
  font-weight: 700;
  text-transform: uppercase;
  background: rgba(124, 58, 237, 0.15);
  color: #7c3aed;
  padding: 1px 4px;
  border-radius: 3px;
  vertical-align: middle;
}

.dt-meta {
  font-size: 10px;
  color: var(--vp-c-text-3);
  padding: 5px 12px 7px;
  border-top: 1px solid var(--vp-c-border-light);
}

/* ── Arrow ───────────────────────────────────────────── */
.dt-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-top: 30px;
}

.dt-arrow-icon {
  font-size: 24px;
  color: #7c3aed;
  font-weight: 700;
  line-height: 1;
}

.dt-arrow-label {
  font-size: 10px;
  font-weight: 600;
  color: #7c3aed;
  text-align: center;
  white-space: nowrap;
  max-width: 80px;
  line-height: 1.3;
}
</style>
