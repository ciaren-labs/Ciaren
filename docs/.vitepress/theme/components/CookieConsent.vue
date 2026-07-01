<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { withBase } from 'vitepress'

// Must match the key read by the inline loader script in config.ts.
const CONSENT_KEY = 'ciaren-analytics-consent'

const visible = ref(false)

onMounted(() => {
  // Only ask when analytics is configured for this build (the inline loader
  // exists) and the visitor hasn't already made a choice.
  const loader = (window as any).__ciarenLoadAnalytics
  if (typeof loader !== 'function') return
  try {
    if (localStorage.getItem(CONSENT_KEY)) return
  } catch {
    // No storage means no way to remember a choice — don't nag on every page.
    return
  }
  visible.value = true
})

function choose(granted: boolean) {
  try {
    localStorage.setItem(CONSENT_KEY, granted ? 'granted' : 'denied')
  } catch {
    // Ignore: worst case the banner shows again on the next visit.
  }
  if (granted) (window as any).__ciarenLoadAnalytics?.()
  visible.value = false
}
</script>

<template>
  <Transition name="cookie-banner">
    <aside
      v-if="visible"
      class="cookie-banner"
      role="dialog"
      aria-live="polite"
      aria-label="Analytics consent"
    >
      <p class="cookie-banner-text">
        🍪 Mind if we count your visit? Anonymous analytics help us see which
        docs pages are useful — no ads, nothing sold or shared.
        <a :href="withBase('/legal/privacy')">Privacy policy</a>
      </p>
      <div class="cookie-banner-actions">
        <button type="button" class="cookie-btn is-accept" @click="choose(true)">
          Sure
        </button>
        <button type="button" class="cookie-btn is-decline" @click="choose(false)">
          No thanks
        </button>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.cookie-banner {
  position: fixed;
  bottom: 16px;
  left: 16px;
  z-index: 100;
  max-width: 340px;
  padding: 14px 16px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  background: var(--vp-c-bg-elv);
  box-shadow: var(--vp-shadow-3);
}

.cookie-banner-text {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--vp-c-text-1);
}

.cookie-banner-text a {
  color: var(--vp-c-brand-1);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.cookie-banner-actions {
  display: flex;
  gap: 8px;
}

.cookie-btn {
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  cursor: pointer;
  transition:
    background-color 0.2s,
    color 0.2s,
    border-color 0.2s;
}

.cookie-btn.is-accept {
  border: 1px solid var(--vp-c-brand-2);
  background: var(--vp-c-brand-2);
  color: #fff;
}

.cookie-btn.is-accept:hover {
  border-color: var(--vp-c-brand-3);
  background: var(--vp-c-brand-3);
}

.cookie-btn.is-decline {
  border: 1px solid var(--vp-c-divider);
  background: transparent;
  color: var(--vp-c-text-2);
}

.cookie-btn.is-decline:hover {
  border-color: var(--vp-c-text-3);
  color: var(--vp-c-text-1);
}

@media (max-width: 480px) {
  .cookie-banner {
    right: 16px;
    max-width: none;
  }
}

.cookie-banner-enter-active,
.cookie-banner-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.cookie-banner-enter-from,
.cookie-banner-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (prefers-reduced-motion: reduce) {
  .cookie-banner-enter-active,
  .cookie-banner-leave-active {
    transition: none;
  }
}
</style>
