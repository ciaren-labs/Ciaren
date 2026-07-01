import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'

import './styles/variables.css'
import './styles/custom.css'

import FlowPipeline from './components/FlowPipeline.vue'
import NodeCategoryGrid from './components/NodeCategoryGrid.vue'
import DataTransform from './components/DataTransform.vue'
import ForkJoin from './components/ForkJoin.vue'
import ScheduleCycle from './components/ScheduleCycle.vue'
import ParamFlow from './components/ParamFlow.vue'
import DomainModel from './components/DomainModel.vue'
import SidebarToggles from './components/SidebarToggles.vue'
import CookieConsent from './components/CookieConsent.vue'

export default {
  extends: DefaultTheme,
  Layout: () => {
    return h(DefaultTheme.Layout, null, {
      'layout-top': () => h(SidebarToggles),
      'layout-bottom': () => h(CookieConsent),
    })
  },
  enhanceApp({ app }) {
    app.component('FlowPipeline', FlowPipeline)
    app.component('NodeCategoryGrid', NodeCategoryGrid)
    app.component('DataTransform', DataTransform)
    app.component('ForkJoin', ForkJoin)
    app.component('ScheduleCycle', ScheduleCycle)
    app.component('ParamFlow', ParamFlow)
    app.component('DomainModel', DomainModel)
  },
} satisfies Theme
