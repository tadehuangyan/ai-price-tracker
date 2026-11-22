/**
 * 全局布局壳：顶栏（品牌 / 降价提醒铃铛 / 用户菜单）+ 侧栏导航 + 主内容区。
 * 负责提醒未读数的拉取与已读联动，以及路由页面的过渡动效编排。
 */
<template>
  <el-container class="layout">
    <!-- ============ 标本馆顶栏 ============ -->
    <el-header class="layout-header">
      <div class="layout-brand" @click="router.push('/')">
        <h1 class="brand-title">
          <span class="brand-cn" ref="brandRef">价迹</span>
          <span class="brand-en">PRICETRACE</span>
        </h1>
        <div class="brand-sub">商品历史价格追踪 · SPECIMEN ARCHIVE</div>
      </div>

      <div class="layout-kicker kicker">
        <span class="pin-dot"></span>CASE FILE · 价格观察档案
        <span class="kicker-slash">/</span>
        <span class="layout-live"><i class="live-dot"></i>实时采集中</span>
      </div>

      <div class="layout-right">
        <el-badge :value="unread" :hidden="unread === 0" class="bell" type="danger">
          <span class="bell-wrap" :class="{ 'is-ringing': unread > 0 }" @click="openAlerts">
            <el-icon :size="20"><Bell /></el-icon>
          </span>
        </el-badge>
        <el-dropdown @command="onUserCmd">
          <span class="user-entry">
            <el-avatar :size="28">{{ avatarText }}</el-avatar>
            <span class="user-name">{{ auth.user?.nickname || auth.user?.username }}</span>
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

    <el-container class="layout-body">
      <!-- ============ 标本柜索引（侧栏） ============ -->
      <el-aside width="220px" class="layout-aside">
        <div class="aside-plate">
          <img class="deco deco-flower" src="/deco/flower-sprig.png" alt="" aria-hidden="true" />
          <span class="tape aside-tape"></span>
          <span class="pin aside-pin" ref="platePinRef"></span>
          <div class="kicker"><span class="pin-dot"></span>CABINET INDEX</div>
          <div class="aside-plate-title">标本柜索引</div>
          <div class="aside-plate-note annot">按类目取阅标本</div>
        </div>

        <el-menu :default-active="active" router class="layout-menu">
          <el-menu-item index="/">
            <span class="menu-no">01</span>
            <el-icon><Search /></el-icon>
            <span class="menu-label">商品查询</span>
            <span class="menu-plate">PLATE Ⅰ</span>
          </el-menu-item>
          <el-menu-item index="/tracking">
            <span class="menu-no">02</span>
            <el-icon><Timer /></el-icon>
            <span class="menu-label">价格追踪</span>
            <span class="menu-plate">PLATE Ⅱ</span>
          </el-menu-item>
          <el-menu-item index="/compare">
            <span class="menu-no">03</span>
            <el-icon><DataLine /></el-icon>
            <span class="menu-label">价格对比</span>
            <span class="menu-plate">PLATE Ⅲ</span>
          </el-menu-item>
          <el-menu-item index="/advisor">
            <span class="menu-no">04</span>
            <el-icon><MagicStick /></el-icon>
            <span class="menu-label">AI 智能导购</span>
            <span class="menu-plate">PLATE Ⅳ</span>
          </el-menu-item>
          <el-menu-item v-if="auth.isAdmin" index="/admin">
            <span class="menu-no">05</span>
            <el-icon><Setting /></el-icon>
            <span class="menu-label">系统管理</span>
            <span class="menu-plate">PLATE Ⅴ</span>
          </el-menu-item>
        </el-menu>

        <div class="aside-foot colophon">
          SPECIMEN ARCHIVE · 价格观察档案
          <img class="deco deco-beetle" src="/deco/beetle.png" alt="" aria-hidden="true" />
        </div>
      </el-aside>

      <!-- ============ 标本台（主内容） ============ -->
      <el-main class="layout-main">
        <div class="layout-rule" aria-hidden="true"></div>
        <div class="layout-paper">
          <router-view v-slot="{ Component }">
            <transition name="layout-page" mode="out-in">
              <!-- 商品查询页保持存活：切走再回来不重新拉数据、不重置筛选状态 -->
              <keep-alive include="Home">
                <component :is="Component" />
              </keep-alive>
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>

    <!-- ============ 采集记录（降价提醒） ============ -->
    <el-drawer v-model="alertDrawer" size="400px" class="layout-drawer">
      <template #header>
        <div class="drawer-head">
          <div class="kicker"><span class="pin-dot"></span>COLLECTION LOG</div>
          <div class="drawer-title">降价提醒 · 采集记录</div>
        </div>
      </template>
      <div class="drawer-body" ref="drawerBodyRef">
        <div class="drawer-tools">
          <span class="annot drawer-note">红笔者为尚未过目之新报</span>
          <el-button size="small" @click="readAll">全部已读</el-button>
        </div>
        <el-empty v-if="!alerts.length" description="暂无采集记录" />
        <!-- 提醒条目循环：点击单条即标记已读，红点/红字表示未读 -->
        <div v-for="(a, i) in alerts" :key="a.id" class="alert-item" @click="markRead(a)">
          <div class="alert-top">
            <span class="kicker">No.{{ String(alerts.length - i).padStart(3, '0') }}</span>
            <span v-if="!a.is_read" class="alert-dot"></span>
          </div>
          <div class="alert-msg" :class="{ unread: !a.is_read }">{{ a.message }}</div>
          <div class="muted">{{ a.created_at }}</div>
        </div>
      </div>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { gsap } from 'gsap'
import api from '../api'
import { useAuthStore } from '../store'
import { splitReveal, pinPress, reducedMotion } from '../anim'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// 侧栏菜单高亮项：取路由一级路径与菜单 index 匹配
const active = computed(() => '/' + (route.path.split('/')[1] || ''))
// 头像占位文字：昵称/用户名首字
const avatarText = computed(() => (auth.user?.nickname || auth.user?.username || '?').slice(0, 1))

// 降价提醒抽屉的可见性
const alertDrawer = ref(false)
// 降价提醒（采集记录）列表
const alerts = ref<any[]>([])
// 未读提醒数：驱动铃铛角标与摇铃动效
const unread = computed(() => alerts.value.filter((a) => !a.is_read).length)

// 拉取降价提醒列表（未登录时跳过；接口失败静默，不影响布局渲染）
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
// 点击单条提醒 -> 标记已读（已读的不再重复请求）
async function markRead(a: any) {
  if (a.is_read) return
  await api.post(`/api/tracking/alerts/${a.id}/read`)
  a.is_read = true
}
// 一键全部标记已读：服务端批量置读后同步本地状态
async function readAll() {
  await api.post('/api/tracking/alerts/read-all')
  alerts.value.forEach((a) => (a.is_read = true))
  ElMessage.success('已全部标记为已读')
}
// 用户下拉命令分发：退出登录 / 进入系统管理 / 进入个人中心
function onUserCmd(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'admin') router.push('/admin')
  else router.push('/profile')
}
onMounted(loadAlerts)

/* ================= 动效编排（仅动效，不涉及业务逻辑） ================= */
// 品牌标题 DOM：入场拆字动效挂载点
const brandRef = ref<HTMLElement | null>(null)
// 侧栏图钉 DOM：按压动效挂载点
const platePinRef = ref<HTMLElement | null>(null)
// 抽屉内容容器 DOM：提醒条目入场动效的作用域
const drawerBodyRef = ref<HTMLElement | null>(null)

// 抽屉打开后对提醒条目做逐条上浮入场（尊重 reduced-motion 设置）
function playDrawerStagger() {
  const items = drawerBodyRef.value?.querySelectorAll<HTMLElement>('.alert-item')
  if (!items || !items.length || reducedMotion) return
  gsap.fromTo(
    items,
    { opacity: 0, y: 18 },
    { opacity: 1, y: 0, duration: 0.55, stagger: 0.08, ease: 'power3.out' }
  )
}

// 抽屉打开时等 DOM 更新完毕再播放条目入场动效
watch(alertDrawer, async (open) => {
  if (!open) return
  await nextTick()
  playDrawerStagger()
})

onMounted(() => {
  splitReveal(brandRef.value)
  pinPress(platePinRef.value, 0.6)
})

// 卸载时终止提醒条目的 GSAP 补间，避免动效实例残留
onUnmounted(() => {
  const items = drawerBodyRef.value?.querySelectorAll<HTMLElement>('.alert-item')
  if (items && items.length) gsap.killTweensOf(Array.from(items))
})
</script>

<style scoped>
.layout {
  height: 100vh;
}

/* ============ 顶栏 ============ */
.layout .layout-header {
  --el-header-height: auto;
  height: auto;
  display: flex;
  align-items: center;
  gap: 26px;
  padding: 14px 28px 12px;
  background: var(--paper-2);
  border-bottom: 1px solid var(--line);
}
.layout-brand {
  cursor: pointer;
}
.brand-title {
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 12px;
  line-height: 1.15;
}
.brand-cn {
  font-family: var(--serif);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ink);
}
.brand-en {
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.28em;
  color: var(--ink-soft);
}
.brand-sub {
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--ink-faint);
}
.layout-kicker {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 22px;
  margin-right: auto;
}
.kicker-slash {
  color: var(--line-strong);
}
.layout-live {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--green);
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  animation: layout-live 1.9s ease-in-out infinite;
}
@keyframes layout-live {
  0%, 100% { opacity: 0.35; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.layout-right {
  display: flex;
  align-items: center;
  gap: 22px;
}
.bell-wrap {
  display: inline-flex;
  padding: 6px;
  border-radius: var(--radius);
  cursor: pointer;
  color: var(--ink-soft);
  transition: color 0.25s, background 0.25s;
}
.bell-wrap:hover {
  color: var(--green);
  background: var(--green-soft);
}
.bell-wrap.is-ringing {
  animation: layout-bell-shake 2.8s ease-in-out infinite;
  transform-origin: 50% 15%;
}
@keyframes layout-bell-shake {
  0%, 55%, 100% { transform: rotate(0); }
  10% { transform: rotate(14deg); }
  20% { transform: rotate(-11deg); }
  30% { transform: rotate(7deg); }
  40% { transform: rotate(-4deg); }
  48% { transform: rotate(2deg); }
}
.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  color: var(--ink);
  font-size: 13px;
}
.user-entry :deep(.el-avatar) {
  background: var(--green);
  color: var(--paper-2);
  font-family: var(--serif);
}
.user-name {
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ============ 侧栏：标本柜索引 ============ */
.layout-body {
  min-height: 0;
}
.layout .layout-aside {
  background: var(--paper);
  border-right: 1px solid var(--line);
  padding: 18px 0 14px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.aside-plate {
  position: relative;
  margin: 10px 14px 18px;
  padding: 15px 12px 12px;
  background: var(--paper-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}
.aside-plate::before {
  content: "";
  position: absolute;
  inset: 4px;
  border: 1px solid rgba(185, 170, 142, 0.3);
  pointer-events: none;
}
.aside-tape {
  top: -11px;
  left: 50%;
  width: 62px;
  transform: translateX(-50%) rotate(-2deg);
}
.aside-pin {
  top: 9px;
  right: 9px;
}
.aside-plate-title {
  font-family: var(--serif);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.14em;
  margin: 7px 0 3px;
  color: var(--ink);
}
.aside-plate-note {
  font-size: 11px;
  letter-spacing: 0.1em;
}
.layout-menu :deep(.el-menu-item) {
  padding: 0 10px;
  gap: 8px;
  height: 44px;
  line-height: 44px;
  position: relative;
}
.layout-menu :deep(.el-menu-item.is-active)::after {
  content: "";
  position: absolute;
  right: 6px;
  top: 50%;
  width: 7px;
  height: 7px;
  margin-top: -3.5px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #d98b66, var(--pin) 65%);
  box-shadow: 0 1px 2px rgba(90, 60, 35, 0.35);
}
.menu-no {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--ink-faint);
}
.menu-label {
  flex: 1;
}
.menu-plate {
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.12em;
  color: var(--ink-faint);
  margin-right: 14px;
  text-transform: uppercase;
}
.layout-menu :deep(.el-menu-item.is-active) .menu-no,
.layout-menu :deep(.el-menu-item.is-active) .menu-plate {
  color: var(--green);
}
.aside-foot {
  position: relative;
  margin: auto 16px 2px;
  padding-top: 12px;
  padding-right: 54px;
  border-top: 1px dashed var(--line);
}

/* —— 透明装饰素材 —— */
.deco {
  position: absolute;
  pointer-events: none;
  user-select: none;
  z-index: 1;
}
.deco-flower {
  right: -12px;
  bottom: -18px;
  width: 88px;
  transform: rotate(-7deg);
  opacity: 0.75;
}
.deco-beetle {
  right: -6px;
  bottom: -4px;
  width: 72px;
  transform: rotate(8deg);
  opacity: 0.7;
}

/* ============ 主内容：标本台 ============ */
.layout .layout-main {
  padding: 0 26px 30px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.layout-rule {
  height: 3px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line-strong);
  margin: 0 2px;
}
.layout-paper {
  margin-top: 16px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  min-height: 60vh;
  /* 纵向 flex 把确定高度传给页面根（聊天页等整屏布局依赖它，避免外层滚动） */
  flex: 1;
  display: flex;
  flex-direction: column;
}
.layout-page-enter-active,
.layout-page-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}
.layout-page-enter-from {
  opacity: 0;
  transform: translateY(14px);
}
.layout-page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ============ 采集记录 drawer ============ */
.drawer-head .drawer-title {
  font-family: var(--serif);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-top: 5px;
  color: var(--ink);
}
.drawer-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--line);
}
.drawer-note {
  font-size: 12px;
}
.alert-item {
  position: relative;
  padding: 12px 6px 12px 12px;
  border-bottom: 1px dashed var(--line);
  cursor: pointer;
  transition: background 0.25s, transform 0.25s;
}
.alert-item:hover {
  background: var(--green-soft);
  transform: translateX(3px);
}
.alert-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.alert-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--pin);
  box-shadow: 0 1px 2px rgba(176, 96, 60, 0.4);
}
.alert-msg {
  font-family: var(--kai);
  font-size: 14px;
  letter-spacing: 0.03em;
  color: var(--ink-soft);
}
.alert-msg.unread {
  color: var(--pin);
  font-weight: 700;
}
</style>
