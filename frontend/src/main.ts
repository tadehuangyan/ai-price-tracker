/**
 * 应用入口：创建 Vue 应用实例，注册 Element Plus 图标、Pinia 状态管理与路由，最后挂载到页面。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
// 全局注册 Element Plus 全部图标组件，模板中可直接按组件名使用
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as any)
}
// 依次安装：Pinia 状态管理 → 路由 → Element Plus（中文语言包，保证日期/分页等组件文案为中文）
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
