import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './store'

const router = createRouter({
  history: createWebHistory(),
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

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLogin) return '/login'
  if (to.path === '/admin' && !auth.isAdmin) return '/'
})

export default router
