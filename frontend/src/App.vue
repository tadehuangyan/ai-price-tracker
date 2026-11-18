<template>
  <router-view v-slot="{ Component }">
    <!-- :duration 显式给定过渡时长：不依赖 transitionend 回调，
         避免标签页被节流时过渡卡在 enter-from（opacity:0）导致页面隐形、点击“无响应” -->
    <transition name="app-fade" mode="out-in" :duration="320">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup lang="ts">
/**
 * 根组件：只保留路由出口，为页面切换提供统一的淡入淡出过渡，
 * 并在路由切换后刷新 ScrollTrigger，保证滚动入场动画在新页面正常触发。
 */
import { nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { refreshScroll } from './anim'

const route = useRoute()

// 路由切换后刷新 ScrollTrigger（anim.ts 的 revealOnScroll 由各处自行管理）
watch(
  () => route.path,
  async () => {
    await nextTick()
    refreshScroll()
  }
)
</script>

<style scoped>
/* 路由切换过渡：离开时淡出上移，进入时淡入下移，配合 :duration 320ms */
.app-fade-enter-active,
.app-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.app-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.app-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
