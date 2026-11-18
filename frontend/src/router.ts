/**
 * 路由配置与全局守卫：登录页独立，其余业务页面挂在主布局 Layout 下（视图组件懒加载），
 * 并统一做登录态与管理员权限校验。
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './store'

const router = createRouter({
  history: createWebHistory(),
  // 路由表：除 /login 外均嵌套在 Layout 主布局中，组件按需懒加载以减小首屏体积
  routes: [
    { path: '/login', component: () => import('./views/Login.vue') },
    {
      path: '/',
      component: () => import('./views/Layout.vue'),
      children: [
        { path: '', component: () => import('./views/Home.vue') },
        { path: 'product/:id', component: () => import('./views/ProductDetail.vue') },
        { path: 'tracking', component: () => import('./views/Tracking.vue') },
        { path: 'compare', component: () => import('./views/Compare.vue') },
        { path: 'advisor', component: () => import('./views/Advisor.vue') },
        { path: 'admin', component: () => import('./views/Admin.vue') },
        { path: 'profile', component: () => import('./views/Profile.vue') },
      ],
    },
  ],
})

// 全局前置守卫：未登录访问任何页面一律跳转登录页；/admin 仅限管理员，否则回首页
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLogin) return '/login'
  if (to.path === '/admin' && !auth.isAdmin) return '/'
})

export default router
