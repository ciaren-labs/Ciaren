<script setup lang="ts">
// No props — this is a static wireframe of the Ciaren editor UI.
</script>

<template>
  <div class="el-wrapper">
    <div class="el-caption">Ciaren Editor Layout</div>

    <div class="el-editor">
      <!-- Left: Node Palette -->
      <aside class="el-palette">
        <div class="el-panel-label">Node Palette</div>
        <div class="el-palette-section">
          <div class="el-palette-group el-color-input">📥 Input</div>
          <div class="el-palette-item">CSV / Excel / Parquet</div>
          <div class="el-palette-item">SQL</div>
        </div>
        <div class="el-palette-section">
          <div class="el-palette-group el-color-clean">🧹 Clean</div>
          <div class="el-palette-item">Drop Columns</div>
          <div class="el-palette-item">Filter Rows</div>
          <div class="el-palette-item">Fill Nulls</div>
          <div class="el-palette-item">…</div>
        </div>
        <div class="el-palette-section">
          <div class="el-palette-group el-color-transform">⚡ Transform</div>
          <div class="el-palette-item">Group By</div>
          <div class="el-palette-item">Join</div>
          <div class="el-palette-item">Pivot</div>
          <div class="el-palette-item">…</div>
        </div>
        <div class="el-palette-section">
          <div class="el-palette-group el-color-output">📤 Output</div>
          <div class="el-palette-item">CSV / Excel</div>
          <div class="el-palette-item">SQL</div>
        </div>
      </aside>

      <!-- Center: Canvas -->
      <main class="el-canvas">
        <div class="el-panel-label">Canvas (drag &amp; drop)</div>
        <div class="el-flow">
          <div class="el-node el-color-input">📥 CSV Input</div>
          <div class="el-edge-h">──→</div>
          <div class="el-node el-color-clean">🧹 Drop Nulls</div>
          <div class="el-edge-h">──→</div>
          <div class="el-node el-color-transform">⚡ Group By</div>
          <div class="el-edge-h">──→</div>
          <div class="el-node el-color-output">📤 CSV Output</div>
        </div>
        <div class="el-toolbar">
          <button class="el-btn el-btn-run">▶ Run</button>
          <button class="el-btn el-btn-export">⬇ Export</button>
          <button class="el-btn el-btn-schedule">⏰ Schedule</button>
        </div>
      </main>

      <!-- Right: Config + Preview -->
      <aside class="el-right">
        <div class="el-config">
          <div class="el-panel-label">Config Panel</div>
          <div class="el-config-row">
            <span class="el-config-key">Group by</span>
            <span class="el-config-val">region</span>
          </div>
          <div class="el-config-row">
            <span class="el-config-key">Aggregate</span>
            <span class="el-config-val">sum(amount)</span>
          </div>
        </div>
        <div class="el-preview">
          <div class="el-panel-label">Live Preview</div>
          <table class="el-preview-table">
            <thead>
              <tr><th>region</th><th>amount</th></tr>
            </thead>
            <tbody>
              <tr><td>North</td><td>330.50</td></tr>
              <tr><td>South</td><td>89.00</td></tr>
              <tr><td>Unknown</td><td>42.25</td></tr>
            </tbody>
          </table>
          <div class="el-preview-meta">3 rows · 2 cols · updated live</div>
        </div>
      </aside>
    </div>

    <div class="el-legend">
      <span class="el-legend-dot el-color-input"></span> Input
      <span class="el-legend-dot el-color-clean" style="margin-left:12px"></span> Clean
      <span class="el-legend-dot el-color-transform" style="margin-left:12px"></span> Transform
      <span class="el-legend-dot el-color-output" style="margin-left:12px"></span> Output
    </div>
  </div>
</template>

<style scoped>
/* ── Outer wrapper ───────────────────────────────────── */
.el-wrapper {
  margin: 28px 0;
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  overflow: hidden;
  font-family: var(--vp-font-family-base);
}

.el-caption {
  background: var(--vp-c-bg-mute);
  border-bottom: 1px solid var(--vp-c-border);
  padding: 6px 16px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-2);
}

/* ── 3-column editor layout ──────────────────────────── */
.el-editor {
  display: grid;
  grid-template-columns: 170px 1fr 200px;
  min-height: 280px;
  background: var(--vp-c-bg);
}

@media (max-width: 720px) {
  .el-editor {
    grid-template-columns: 1fr;
  }
}

/* ── Shared panel label ──────────────────────────────── */
.el-panel-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-3);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--vp-c-border-light);
}

/* ── Palette ─────────────────────────────────────────── */
.el-palette {
  border-right: 1px solid var(--vp-c-border);
  padding: 14px 12px;
  background: var(--vp-c-bg-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.el-palette-section {
  margin-bottom: 4px;
}

.el-palette-group {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  margin-bottom: 3px;
}

.el-palette-item {
  font-size: 11px;
  color: var(--vp-c-text-2);
  padding: 2px 8px 2px 16px;
  cursor: default;
}

/* ── Canvas ──────────────────────────────────────────── */
.el-canvas {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.el-flow {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
  padding: 14px;
  background: var(--vp-c-bg-mute);
  border: 1px dashed var(--vp-c-border);
  border-radius: 8px;
}

.el-node {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  border-left: 3px solid transparent;
  background: var(--vp-c-bg);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  white-space: nowrap;
}

.el-edge-h {
  font-size: 13px;
  color: var(--vp-c-text-3);
  white-space: nowrap;
}

.el-toolbar {
  display: flex;
  gap: 8px;
}

.el-btn {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 5px;
  border: 1px solid var(--vp-c-border);
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  cursor: default;
}

.el-btn-run {
  background: #7c3aed;
  color: #fff;
  border-color: #7c3aed;
}

/* ── Right panel ─────────────────────────────────────── */
.el-right {
  border-left: 1px solid var(--vp-c-border);
  display: flex;
  flex-direction: column;
}

.el-config {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--vp-c-border);
  background: var(--vp-c-bg-soft);
}

.el-config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px solid var(--vp-c-border-light);
}

.el-config-key {
  color: var(--vp-c-text-2);
}

.el-config-val {
  font-weight: 600;
  color: var(--vp-c-brand-1);
  font-family: var(--vp-font-family-mono);
  font-size: 11px;
}

.el-preview {
  padding: 14px 14px 12px;
  flex: 1;
}

.el-preview-table {
  width: 100%;
  font-size: 11px;
  border-collapse: collapse;
  margin: 6px 0 6px;
}

.el-preview-table th,
.el-preview-table td {
  border: 1px solid var(--vp-c-border);
  padding: 4px 8px;
  text-align: left;
}

.el-preview-table th {
  background: var(--vp-c-bg-mute);
  font-weight: 700;
  color: var(--vp-c-text-2);
}

.el-preview-meta {
  font-size: 10px;
  color: var(--vp-c-text-3);
  margin-top: 4px;
}

/* ── Category colours ────────────────────────────────── */
.el-color-input    { border-left-color: #059669 !important; color: #059669; }
.el-color-clean    { border-left-color: #0284c7 !important; color: #0284c7; }
.el-color-transform { border-left-color: #7c3aed !important; color: #7c3aed; }
.el-color-output   { border-left-color: #d97706 !important; color: #d97706; }

.el-palette-group.el-color-input    { background: rgba(5,150,105,0.1); }
.el-palette-group.el-color-clean    { background: rgba(2,132,199,0.1); }
.el-palette-group.el-color-transform { background: rgba(124,58,237,0.1); }
.el-palette-group.el-color-output   { background: rgba(217,119,6,0.1); }

/* ── Legend ──────────────────────────────────────────── */
.el-legend {
  padding: 8px 16px;
  font-size: 11px;
  color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft);
  border-top: 1px solid var(--vp-c-border);
  display: flex;
  align-items: center;
  gap: 4px;
}

.el-legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.el-legend-dot.el-color-input    { background: #059669; }
.el-legend-dot.el-color-clean    { background: #0284c7; }
.el-legend-dot.el-color-transform { background: #7c3aed; }
.el-legend-dot.el-color-output   { background: #d97706; }
</style>
