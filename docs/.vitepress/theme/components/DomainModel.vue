<script setup lang="ts">
// Static diagram of the Ciaren domain model
</script>

<template>
  <div class="dm-wrapper">
    <div class="dm-caption">Ciaren Domain Model</div>

    <div class="dm-graph">
      <!-- Row 1 -->
      <div class="dm-row dm-row-top">
        <div class="dm-entity dm-entity--project">
          <div class="dm-entity-icon">📁</div>
          <div class="dm-entity-name">Project</div>
          <div class="dm-entity-fields">
            <div class="dm-field">name</div>
            <div class="dm-field">description</div>
          </div>
        </div>
      </div>

      <!-- Project has-many Datasets + Flows -->
      <div class="dm-row dm-row-connector">
        <div class="dm-connector-col">
          <div class="dm-line-v"></div>
          <div class="dm-line-h dm-line-h--split">
            <div class="dm-line-seg"></div>
            <div class="dm-line-seg"></div>
          </div>
        </div>
      </div>

      <!-- Row 2: Dataset + Flow -->
      <div class="dm-row dm-row-mid">
        <div class="dm-entity dm-entity--dataset">
          <div class="dm-entity-icon">📊</div>
          <div class="dm-entity-name">Dataset</div>
          <div class="dm-entity-fields">
            <div class="dm-field">name · source_type</div>
            <div class="dm-field">schema · sample</div>
            <div class="dm-field dm-field--version">has many Versions</div>
          </div>
        </div>

        <div class="dm-gap"></div>

        <div class="dm-entity dm-entity--flow">
          <div class="dm-entity-icon">⚡</div>
          <div class="dm-entity-name">Flow</div>
          <div class="dm-entity-fields">
            <div class="dm-field">name · graph_json</div>
            <div class="dm-field dm-field--note">nodes + edges + parameters</div>
          </div>
        </div>
      </div>

      <!-- Dataset ← input node ← Flow; Flow → Run/Schedule -->
      <div class="dm-row dm-row-connector">
        <div class="dm-connector-col dm-connector-col--right">
          <div class="dm-line-h dm-line-h--split">
            <div class="dm-line-seg"></div>
            <div class="dm-line-seg"></div>
          </div>
          <div class="dm-line-v"></div>
        </div>
      </div>

      <!-- Row 3: Run + Schedule -->
      <div class="dm-row dm-row-bottom">
        <div class="dm-entity dm-entity--run">
          <div class="dm-entity-icon">▶</div>
          <div class="dm-entity-name">Run</div>
          <div class="dm-entity-fields">
            <div class="dm-field">status · engine</div>
            <div class="dm-field">started_at · finished_at</div>
            <div class="dm-field dm-field--note">per-node results · logs</div>
            <div class="dm-field dm-field--note">resolved dataset versions</div>
          </div>
        </div>

        <div class="dm-gap"></div>

        <div class="dm-entity dm-entity--schedule">
          <div class="dm-entity-icon">⏰</div>
          <div class="dm-entity-name">Schedule</div>
          <div class="dm-entity-fields">
            <div class="dm-field">cron · timezone</div>
            <div class="dm-field">enabled · catch_up</div>
            <div class="dm-field dm-field--note">fires Runs automatically</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="dm-legend">
      <span class="dm-dot dm-dot--project"></span> Project
      <span class="dm-dot dm-dot--dataset" style="margin-left:14px"></span> Dataset
      <span class="dm-dot dm-dot--flow" style="margin-left:14px"></span> Flow
      <span class="dm-dot dm-dot--run" style="margin-left:14px"></span> Run
      <span class="dm-dot dm-dot--schedule" style="margin-left:14px"></span> Schedule
    </div>
  </div>
</template>

<style scoped>
/* ── Outer wrapper ─────────────────────────────────── */
.dm-wrapper {
  margin: 28px 0;
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  overflow: hidden;
}

.dm-caption {
  background: var(--vp-c-bg-mute);
  border-bottom: 1px solid var(--vp-c-border);
  padding: 6px 16px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-2);
}

/* ── Graph area ────────────────────────────────────── */
.dm-graph {
  padding: 20px 24px;
  background: var(--vp-c-bg-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

/* ── Rows ──────────────────────────────────────────── */
.dm-row {
  width: 100%;
  display: flex;
  justify-content: center;
}

.dm-row-top    { margin-bottom: 0; }
.dm-row-mid    { gap: 20px; }
.dm-row-bottom { gap: 20px; }

/* ── Entities ──────────────────────────────────────── */
.dm-entity {
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid;
  background: var(--vp-c-bg);
  min-width: 180px;
  flex: 0 1 200px;
}

.dm-entity-icon {
  font-size: 20px;
  line-height: 1;
  margin-bottom: 6px;
}

.dm-entity-name {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
}

.dm-field {
  font-size: 11px;
  color: var(--vp-c-text-2);
  font-family: var(--vp-font-family-mono);
  padding: 1px 0;
  line-height: 1.5;
}

.dm-field--note {
  font-style: italic;
  font-family: var(--vp-font-family-base);
  color: var(--vp-c-text-3);
}

.dm-field--version {
  color: #0284c7;
  font-style: italic;
  font-family: var(--vp-font-family-base);
}

/* entity colour coding */
.dm-entity--project  { border-color: #7c3aed; }
.dm-entity--dataset  { border-color: #0284c7; }
.dm-entity--flow     { border-color: #059669; }
.dm-entity--run      { border-color: #d97706; }
.dm-entity--schedule { border-color: #4338ca; }

.dm-entity--project  .dm-entity-name { color: #7c3aed; }
.dm-entity--dataset  .dm-entity-name { color: #0284c7; }
.dm-entity--flow     .dm-entity-name { color: #059669; }
.dm-entity--run      .dm-entity-name { color: #d97706; }
.dm-entity--schedule .dm-entity-name { color: #4338ca; }

/* ── Connectors ────────────────────────────────────── */
.dm-row-connector {
  height: 28px;
  position: relative;
}

.dm-connector-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 420px;
}

.dm-connector-col--right {
  flex-direction: column-reverse;
}

.dm-line-v {
  width: 1px;
  height: 14px;
  background: var(--vp-c-border);
}

.dm-line-h--split {
  display: flex;
  width: 220px;
  height: 1px;
  background: var(--vp-c-border);
}

.dm-gap {
  width: 20px;
  flex-shrink: 0;
}

/* ── Legend ────────────────────────────────────────── */
.dm-legend {
  padding: 8px 20px;
  font-size: 11px;
  color: var(--vp-c-text-2);
  background: var(--vp-c-bg);
  border-top: 1px solid var(--vp-c-border);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.dm-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  vertical-align: middle;
}

.dm-dot--project  { background: #7c3aed; }
.dm-dot--dataset  { background: #0284c7; }
.dm-dot--flow     { background: #059669; }
.dm-dot--run      { background: #d97706; }
.dm-dot--schedule { background: #4338ca; }

/* ── Responsive ────────────────────────────────────── */
@media (max-width: 560px) {
  .dm-row-mid, .dm-row-bottom {
    flex-direction: column;
    align-items: center;
  }
  .dm-connector-col { display: none; }
}
</style>
