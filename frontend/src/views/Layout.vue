<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand" @click="router.push('/')">
        <el-icon :size="22"><TrendCharts /></el-icon>
        <span>商品历史价格追踪系统</span>
      </div>
      <div class="right">
        <el-badge :value="unread" :hidden="unread === 0" class="bell" type="danger">
          <el-icon :size="20" style="cursor: pointer" @click="openAlerts"><Bell /></el-icon>
        </el-badge>
        <el-dropdown @command="onUserCmd">
          <span class="user-entry">
            <el-avatar :size="28">{{ avatarText }}</el-avatar>
            <span>{{ auth.user?.nickname || auth.user?.username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item v-if="auth.isAdmin" command="admin">系统管理</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" class="aside">
        <el-menu :default-active="active" router class="menu">
          <el-menu-item index="/"><el-icon><Search /></el-icon>商品查询</el-menu-item>
          <el-menu-item index="/tracking"><el-icon><Timer /></el-icon>价格追踪</el-menu-item>
          <el-menu-item index="/compare"><el-icon><DataLine /></el-icon>价格对比</el-menu-item>
          <el-menu-item index="/advisor"><el-icon><MagicStick /></el-icon>AI 智能导购</el-menu-item>
          <el-menu-item v-if="auth.isAdmin" index="/admin"><el-icon><Setting /></el-icon>系统管理</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer v-model="alertDrawer" title="降价提醒" size="380px">
      <div style="margin-bottom: 10px; text-align: right">
        <el-button size="small" @click="readAll">全部已读</el-button>
      </div>
      <el-empty v-if="!alerts.length" description="暂无提醒" />
      <div v-for="a in alerts" :key="a.id" class="alert-item" @click="markRead(a)">
        <div class="alert-msg" :class="{ unread: !a.is_read }">{{ a.message }}</div>
        <div class="muted">{{ a.created_at }}</div>
      </div>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../store'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const active = computed(() => '/' + (route.path.split('/')[1] || ''))
const avatarText = computed(() => (auth.user?.nickname || auth.user?.username || '?').slice(0, 1))

const alertDrawer = ref(false)
const alerts = ref<any[]>([])
const unread = computed(() => alerts.value.filter((a) => !a.is_read).length)

async function loadAlerts() {
  if (!auth.isLogin) return
  try {
    const { data } = await api.get('/api/tracking/alerts')
    alerts.value = data
  } catch {
    /* ignore */
  }
}
function openAlerts() {
  alertDrawer.value = true
  loadAlerts()
}
async function markRead(a: any) {
  if (a.is_read) return
  await api.post(`/api/tracking/alerts/${a.id}/read`)
  a.is_read = true
}
async function readAll() {
  await api.post('/api/tracking/alerts/read-all')
  alerts.value.forEach((a) => (a.is_read = true))
  ElMessage.success('已全部标记为已读')
}
function onUserCmd(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'admin') router.push('/admin')
  else router.push('/profile')
}
onMounted(loadAlerts)
</script>

<style scoped>
.layout { height: 100vh; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #ebeef5;
}
.brand { display: flex; align-items: center; gap: 8px; font-size: 17px; font-weight: 700; cursor: pointer; color: #409eff; }
.right { display: flex; align-items: center; gap: 20px; }
.user-entry { display: flex; align-items: center; gap: 6px; cursor: pointer; outline: none; }
.aside { background: #fff; border-right: 1px solid #ebeef5; }
.menu { border-right: none; }
.main { padding: 0; overflow-y: auto; }
.alert-item { padding: 10px 4px; border-bottom: 1px dashed #ebeef5; cursor: pointer; }
.alert-msg { font-size: 14px; color: #606266; }
.alert-msg.unread { color: #f56c6c; font-weight: 600; }
</style>
