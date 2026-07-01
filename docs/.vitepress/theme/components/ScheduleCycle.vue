<script setup lang="ts">
// No props — this is a static diagram of the Ciaren scheduler lifecycle.
</script>

<template>
  <div class="sc-wrapper">
    <div class="sc-caption">Scheduler Lifecycle</div>

    <div class="sc-flow">
      <!-- Step 1: Cron fires -->
      <div class="sc-step sc-step--trigger">
        <div class="sc-step-icon">⏰</div>
        <div class="sc-step-body">
          <div class="sc-step-title">Cron fires</div>
          <div class="sc-step-desc">Poller wakes every 30 s, checks <code>next_run_at</code></div>
        </div>
      </div>

      <div class="sc-arrow">↓</div>

      <!-- Step 2: Run executes -->
      <div class="sc-step sc-step--running">
        <div class="sc-step-icon">▶</div>
        <div class="sc-step-body">
          <div class="sc-step-title">Run executes</div>
          <div class="sc-step-desc">Flow runs on the engine; concurrent limit respected</div>
        </div>
      </div>

      <div class="sc-arrow">↓</div>

      <!-- Step 3: Branch -->
      <div class="sc-branches">
        <!-- Success path -->
        <div class="sc-branch">
          <div class="sc-step sc-step--success">
            <div class="sc-step-icon">✓</div>
            <div class="sc-step-body">
              <div class="sc-step-title">Success</div>
              <div class="sc-step-desc">Run recorded; <code>next_run_at</code> advances to next cron slot</div>
            </div>
          </div>
          <div class="sc-arrow sc-arrow--small">↓</div>
          <div class="sc-step sc-step--wait">
            <div class="sc-step-icon">💤</div>
            <div class="sc-step-body">
              <div class="sc-step-title">Wait for next slot</div>
              <div class="sc-step-desc">Failure streak resets</div>
            </div>
          </div>
        </div>

        <!-- Failure path -->
        <div class="sc-branch">
          <div class="sc-step sc-step--failed">
            <div class="sc-step-icon">✗</div>
            <div class="sc-step-body">
              <div class="sc-step-title">Failed</div>
              <div class="sc-step-desc">Streak increments</div>
            </div>
          </div>
          <div class="sc-arrow sc-arrow--small">↓</div>
          <div class="sc-step sc-step--retry">
            <div class="sc-step-icon">↺</div>
            <div class="sc-step-body">
              <div class="sc-step-title">Retry (if max_retries &gt; 0)</div>
              <div class="sc-step-desc">Exponential backoff, capped at 1 h</div>
            </div>
          </div>
          <div class="sc-arrow sc-arrow--small">↓</div>
          <div class="sc-step sc-step--disabled">
            <div class="sc-step-icon">🚫</div>
            <div class="sc-step-body">
              <div class="sc-step-title">Auto-disable (after 5 failures)</div>
              <div class="sc-step-desc">Re-enable in the UI to clear streak</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="sc-legend">
      <span class="sc-dot sc-dot--trigger"></span> Trigger
      <span class="sc-dot sc-dot--success" style="margin-left:14px"></span> Success
      <span class="sc-dot sc-dot--failed" style="margin-left:14px"></span> Failed
      <span class="sc-dot sc-dot--retry" style="margin-left:14px"></span> Retry
      <span class="sc-dot sc-dot--disabled" style="margin-left:14px"></span> Disabled
    </div>
  </div>
</template>

<style scoped>
/* ── Outer wrapper ───────────────────────────────────── */
.sc-wrapper {
  margin: 24px 0;
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  overflow: hidden;
}

.sc-caption {
  background: var(--vp-c-bg-mute);
  border-bottom: 1px solid var(--vp-c-border);
  padding: 6px 16px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-2);
}

/* ── Main flow ───────────────────────────────────────── */
.sc-flow {
  padding: 20px 24px;
  background: var(--vp-c-bg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

/* ── Arrow ───────────────────────────────────────────── */
.sc-arrow {
  font-size: 18px;
  color: var(--vp-c-text-3);
  line-height: 1;
  padding: 2px 0;
}

.sc-arrow--small {
  font-size: 14px;
}

/* ── Step card ───────────────────────────────────────── */
.sc-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 8px;
  border-left: 4px solid;
  background: var(--vp-c-bg-soft);
  min-width: 240px;
  max-width: 320px;
  width: 100%;
}

.sc-step--trigger  { border-left-color: #7c3aed; }
.sc-step--running  { border-left-color: #0284c7; }
.sc-step--success  { border-left-color: #059669; }
.sc-step--wait     { border-left-color: #059669; }
.sc-step--failed   { border-left-color: #dc2626; }
.sc-step--retry    { border-left-color: #d97706; }
.sc-step--disabled { border-left-color: #6b7280; }

.sc-step-icon {
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 1px;
}

.sc-step--trigger  .sc-step-icon { color: #7c3aed; }
.sc-step--running  .sc-step-icon { color: #0284c7; }
.sc-step--success  .sc-step-icon { color: #059669; }
.sc-step--wait     .sc-step-icon { color: #059669; }
.sc-step--failed   .sc-step-icon { color: #dc2626; }
.sc-step--retry    .sc-step-icon { color: #d97706; }
.sc-step--disabled .sc-step-icon { color: #6b7280; }

.sc-step-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  line-height: 1.3;
}

.sc-step-desc {
  font-size: 11px;
  color: var(--vp-c-text-2);
  margin-top: 2px;
  line-height: 1.4;
}

.sc-step-desc code {
  font-size: 10px;
  background: var(--vp-c-bg-mute);
  padding: 1px 4px;
  border-radius: 3px;
}

/* ── Branch split ────────────────────────────────────── */
.sc-branches {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  width: 100%;
  max-width: 720px;
  position: relative;
  padding-top: 8px;
}

.sc-branches::before {
  content: '';
  position: absolute;
  top: 0;
  left: calc(50% - 40px);
  width: 80px;
  height: 1px;
  background: var(--vp-c-border);
}

.sc-branch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.sc-branch::before {
  content: attr(data-label);
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-text-3);
  margin-bottom: 2px;
}

.sc-branch:first-child { border-right: 1px dashed var(--vp-c-border); padding-right: 12px; }
.sc-branch:last-child  { padding-left: 12px; }

/* ── Legend ──────────────────────────────────────────── */
.sc-legend {
  padding: 8px 20px;
  font-size: 11px;
  color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft);
  border-top: 1px solid var(--vp-c-border);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.sc-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  vertical-align: middle;
}

.sc-dot--trigger  { background: #7c3aed; }
.sc-dot--success  { background: #059669; }
.sc-dot--failed   { background: #dc2626; }
.sc-dot--retry    { background: #d97706; }
.sc-dot--disabled { background: #6b7280; }

/* ── Responsive ──────────────────────────────────────── */
@media (max-width: 600px) {
  .sc-branches {
    grid-template-columns: 1fr;
  }
  .sc-branch:first-child {
    border-right: none;
    border-bottom: 1px dashed var(--vp-c-border);
    padding-right: 0;
    padding-bottom: 12px;
  }
  .sc-branch:last-child {
    padding-left: 0;
  }
}
</style>
