<script setup lang="ts">
import { ref, onMounted } from 'vue'

const navOpen = ref(true)
const asideOpen = ref(true)

function applyState() {
  document.documentElement.classList.toggle('ciaren-sidebar-collapsed', !navOpen.value)
  document.documentElement.classList.toggle('ciaren-aside-collapsed', !asideOpen.value)
}

function toggleNav() {
  navOpen.value = !navOpen.value
  localStorage.setItem('ciaren-nav-open', String(navOpen.value))
  applyState()
}

function toggleAside() {
  asideOpen.value = !asideOpen.value
  localStorage.setItem('ciaren-aside-open', String(asideOpen.value))
  applyState()
}

onMounted(() => {
  navOpen.value = localStorage.getItem('ciaren-nav-open') !== 'false'
  asideOpen.value = localStorage.getItem('ciaren-aside-open') !== 'false'
  applyState()
})
</script>

<template>
  <!-- Left nav toggle — only on screens ≥ 960px where sidebar is visible -->
  <button
    class="ciaren-toggle ciaren-toggle--nav"
    :aria-label="navOpen ? 'Collapse navigation' : 'Expand navigation'"
    :title="navOpen ? 'Collapse navigation' : 'Expand navigation'"
    @click="toggleNav"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path v-if="navOpen" d="m15 18-6-6 6-6" />
      <path v-else d="m9 18 6-6-6-6" />
    </svg>
  </button>

  <!-- Right aside toggle — only on screens ≥ 1280px where outline is visible -->
  <button
    class="ciaren-toggle ciaren-toggle--aside"
    :aria-label="asideOpen ? 'Collapse outline' : 'Expand outline'"
    :title="asideOpen ? 'Collapse outline' : 'Expand outline'"
    @click="toggleAside"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path v-if="asideOpen" d="m9 18 6-6-6-6" />
      <path v-else d="m15 18-6-6 6-6" />
    </svg>
  </button>
</template>

<style>
/* Non-scoped so html.ciaren-* overrides can apply */

.ciaren-toggle {
  position: fixed;
  z-index: 29;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-border);
  border-radius: 4px;
  color: var(--vp-c-text-3);
  cursor: pointer;
  padding: 0;
  transition: left 0.25s ease, right 0.25s ease, background 0.15s, color 0.15s, opacity 0.15s;
  opacity: 0.7;
}

.ciaren-toggle:hover {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  opacity: 1;
}

/* Nav toggle: right edge of the sidebar */
.ciaren-toggle--nav {
  left: calc(var(--vp-sidebar-width) - 10px);
}

html.ciaren-sidebar-collapsed .ciaren-toggle--nav {
  left: 8px;
}

/* Aside toggle: fixed at right edge of viewport */
.ciaren-toggle--aside {
  right: 8px;
}

/* Only show on screens where the sidebars are actually visible */
@media (max-width: 959px) {
  .ciaren-toggle--nav {
    display: none;
  }
}

@media (max-width: 1279px) {
  .ciaren-toggle--aside {
    display: none;
  }
}
</style>
