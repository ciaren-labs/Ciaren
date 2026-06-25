import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'

import './styles/variables.css'
import './styles/custom.css'

import FlowPipeline from './components/FlowPipeline.vue'
import NodeCategoryGrid from './components/NodeCategoryGrid.vue'
import EditorLayout from './components/EditorLayout.vue'
import DataTransform from './components/DataTransform.vue'
import ForkJoin from './components/ForkJoin.vue'
import ScheduleCycle from './components/ScheduleCycle.vue'

export default {
  extends: DefaultTheme,
  Layout: () => {
    return h(DefaultTheme.Layout, null, {})
  },
  enhanceApp({ app }) {
    app.component('FlowPipeline', FlowPipeline)
    app.component('NodeCategoryGrid', NodeCategoryGrid)
    app.component('EditorLayout', EditorLayout)
    app.component('DataTransform', DataTransform)
    app.component('ForkJoin', ForkJoin)
    app.component('ScheduleCycle', ScheduleCycle)
  },
} satisfies Theme
