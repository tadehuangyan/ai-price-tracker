<template>
  <router-view v-slot="{ Component }">
    <transition name="app-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup lang="ts">
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
