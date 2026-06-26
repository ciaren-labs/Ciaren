<script setup lang="ts">
import { ref, onMounted } from 'vue'

const navOpen = ref(true)
const asideOpen = ref(true)

function applyState() {
  document.documentElement.classList.toggle('ff-sidebar-collapsed', !navOpen.value)
  document.documentElement.classList.toggle('ff-aside-collapsed', !asideOpen.value)
}

function toggleNav() {
  navOpen.value = !navOpen.value
  localStorage.setItem('ff-nav-open', String(navOpen.value))
  applyState()
}

function toggleAside() {
  asideOpen.value = !asideOpen.value
  localStorage.setItem('ff-aside-open', String(asideOpen.value))
  applyState()
}

onMounted(() => {
  navOpen.value = localStorage.getItem('ff-nav-open') !== 'false'
  asideOpen.value = localStorage.getItem('ff-aside-open') !== 'false'
  applyState()
})
</script>

<template>
  <!-- Left nav toggle — only on screens ≥ 960px where sidebar is visible -->
  <button
    class="ff-toggle ff-toggle--nav"
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
    class="ff-toggle ff-toggle--aside"
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
/* Non-scoped so html.ff-* overrides can apply */

.ff-toggle {
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

.ff-toggle:hover {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  opacity: 1;
}

/* Nav toggle: right edge of the sidebar */
.ff-toggle--nav {
  left: calc(var(--vp-sidebar-width) - 10px);
}

html.ff-sidebar-collapsed .ff-toggle--nav {
  left: 8px;
}

/* Aside toggle: fixed at right edge of viewport */
.ff-toggle--aside {
  right: 8px;
}

/* Only show on screens where the sidebars are actually visible */
@media (max-width: 959px) {
  .ff-toggle--nav {
    display: none;
  }
}

@media (max-width: 1279px) {
  .ff-toggle--aside {
    display: none;
  }
}
</style>
