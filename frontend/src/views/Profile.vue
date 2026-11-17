<template>
  <div class="page" ref="pageEl">
    <div class="page-head">
      <img src="/deco/quill-ink.png" alt="" aria-hidden="true" class="deco deco-quill" />
      <div class="kicker"><span class="pin-dot"></span>PERSONAL FILE · 个人档案</div>
      <h2 class="page-title" ref="titleEl">个人中心</h2>
      <div class="page-sub">身份、凭证与往来信札 · 均记录在案</div>
    </div>

    <!-- 档案速览 -->
    <div class="stat-strip spec-card reveal" data-delay="80" ref="statsEl">
      <div class="stat-item">
        <div class="stat-n"><span :data-count="inbox.total">{{ inbox.total }}</span></div>
        <div class="stat-l kicker">MAILS · 来函</div>
      </div>
      <div class="stat-item">
        <div class="stat-n"><span :data-count="inbox.unread">{{ inbox.unread }}</span></div>
        <div class="stat-l kicker">UNREAD · 未读</div>
      </div>
      <div class="stat-item">
        <div class="stat-n stat-text">{{ auth.isAdmin ? '管理员' : '普通用户' }}</div>
        <div class="stat-l kicker">ROLE · 角色</div>
      </div>
      <div class="stat-item">
        <div class="stat-n stat-text stat-mail">{{ auth.user?.email }}</div>
        <div class="stat-l kicker">E-MAIL · 邮箱</div>
      </div>
    </div>

    <el-tabs v-model="tab" class="profile-tabs">
      <el-tab-pane label="个人资料" name="profile">
        <div class="card spec-card file-card reveal" data-delay="160">
          <div class="kicker"><span class="pin-dot"></span>DOSSIER · 资料卡</div>
          <h3 class="card-title">个人资料</h3>
          <el-form :model="form" label-width="150px">
            <el-form-item>
              <template #label><span class="fld">USERNAME · 用户名</span></template>
              <el-input :model-value="auth.user?.username" disabled />
            </el-form-item>
            <el-form-item>
              <template #label><span class="fld">NICKNAME · 昵称</span></template>
              <el-input v-model="form.nickname" />
            </el-form-item>
            <el-form-item>
              <template #label><span class="fld">E-MAIL · 邮箱</span></template>
              <el-input v-model="form.email" />
            </el-form-item>
            <el-form-item v-if="emailChanged">
              <template #label><span class="fld">MAIL CODE · 邮箱验证码</span></template>
              <div style="display: flex; gap: 8px; width: 100%">
                <el-input v-model="form.email_code" placeholder="6 位验证码" maxlength="6" />
                <el-button :disabled="emailCd > 0" @click="sendEmailCode">
                  {{ emailCd > 0 ? `${emailCd}s` : '发送验证码' }}
                </el-button>
              </div>
              <div class="muted">验证码将模拟投递到新邮箱，可在「我的邮箱」中查看</div>
            </el-form-item>
            <el-form-item>
              <template #label><span class="fld">NEW PWD · 新密码</span></template>
              <el-input v-model="form.password" type="password" show-password placeholder="不修改请留空（>=8 位含字母数字）" />
            </el-form-item>
            <el-form-item v-if="form.password">
              <template #label><span class="fld">PWD CODE · 密码验证码</span></template>
              <div style="display: flex; gap: 8px; width: 100%">
                <el-input v-model="form.password_code" placeholder="6 位验证码" maxlength="6" />
                <el-button :disabled="pwdCd > 0" @click="sendPwdCode">
                  {{ pwdCd > 0 ? `${pwdCd}s` : '发送验证码' }}
                </el-button>
              </div>
              <div class="muted">验证码将模拟投递到当前绑定邮箱（{{ auth.user?.email }}）</div>
            </el-form-item>
            <el-form-item>
              <span class="mag-wrap" ref="saveWrap">
                <el-button type="primary" :loading="loading" @click="save">保存修改</el-button>
              </span>
            </el-form-item>
          </el-form>
          <div class="colophon">角色：{{ auth.isAdmin ? '管理员' : '普通用户' }}</div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="用户画像" name="memo">
        <div class="card spec-card file-card reveal" data-delay="120">
          <div class="kicker"><span class="pin-dot"></span>PROFILE MEMO · 用户画像</div>
          <h3 class="card-title">用户画像</h3>
          <div class="muted memo-desc">
            由 AI 智能导购根据对话自动整理（消费偏好 / 预算区间 / 关注商品 / 购买习惯），也可在此手动修改；
            后续对话中的个性化消费建议会参考这里的内容。
          </div>
          <el-input
            v-model="memoContent"
            type="textarea"
            :rows="14"
            placeholder="暂无画像记录。可直接书写，例如：&#10;## 消费偏好&#10;- 偏好性价比高的手机&#10;## 预算区间&#10;- 手机预算约 3000 元"
          />
          <div class="memo-foot">
            <span class="muted">{{ memoContent.length }} / 20000</span>
            <span class="memo-btns">
              <el-button @click="loadMemo">重新加载</el-button>
              <el-button type="primary" :loading="memoLoading" @click="saveMemo">保存画像</el-button>
            </span>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane name="inbox">
        <template #label>
          我的邮箱
          <el-badge v-if="inbox.unread > 0" :value="inbox.unread" :max="99" style="margin-left: 4px" />
        </template>
        <div class="card spec-card mail-card">
          <div class="kicker"><span class="pin-dot"></span>02 · CORRESPONDENCE · 往来信札</div>
          <div class="card-head-row">
            <h3 class="card-title">我的邮箱（模拟收件箱）</h3>
            <div>
              <el-button size="small" @click="loadInbox">刷新</el-button>
              <el-button size="small" :disabled="!inbox.unread" @click="readAll">全部已读</el-button>
            </div>
          </div>
          <div class="muted" style="margin-bottom: 10px">
            SMTP 端口受限，系统邮件（验证码/降价提醒/订阅确认）不真实外发，而是模拟投递到此收件箱（类比支付宝沙箱）。
          </div>
          <el-table :data="inbox.items" v-loading="inboxLoading" empty-text="暂无邮件" @row-click="openMail">
            <el-table-column width="90">
              <template #default="{ row }">
                <el-tag v-if="!row.is_read" size="small" type="danger">未读</el-tag>
                <el-tag v-else size="small" type="info">已读</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="categoryType(row.category)">{{ row.category_name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="subject" label="主题" show-overflow-tooltip />
            <el-table-column label="验证码" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.code" size="small" type="warning">{{ row.code }}</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="160" />
          </el-table>
          <el-pagination
            v-if="inbox.total > inbox.page_size"
            style="margin-top: 12px; justify-content: flex-end"
            layout="prev, pager, next, total"
            :total="inbox.total"
            :page-size="inbox.page_size"
            :current-page="inbox.page"
            @current-change="loadInbox"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="mailVisible" :title="currentMail?.subject || '邮件详情'" width="560px">
      <div class="muted" style="margin-bottom: 8px">
        发送时间：{{ currentMail?.created_at }} · 收件人：{{ currentMail?.to_email }} · 状态：模拟投递（sent）
      </div>
      <div style="white-space: pre-wrap; line-height: 1.8">{{ currentMail?.body }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'
import { countUp, magnetic, refreshScroll, revealOnScroll, splitReveal } from '../anim'

const auth = useAuthStore()
const tab = ref('profile')
const loading = ref(false)
const form = reactive({
  nickname: auth.user?.nickname || '',
  email: auth.user?.email || '',
  password: '',
  email_code: '',
  password_code: '',
})

const emailChanged = computed(() => form.email !== (auth.user?.email || ''))

function startCd(target: { value: number }) {
  target.value = 60
  const t = setInterval(() => {
    target.value--
    if (target.value <= 0) clearInterval(t)
  }, 1000)
}
const emailCd = ref(0)
const pwdCd = ref(0)

async function sendEmailCode() {
  try {
    const { data } = await api.post('/api/mail/send-code-auth', { email: form.email, purpose: 'email_change' })
    ElMessage.success(data.message || '验证码已模拟投递')
    startCd(emailCd)
    tab.value = 'inbox'
    loadInbox()
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

async function sendPwdCode() {
  try {
    const { data } = await api.post('/api/mail/send-code-auth', { email: auth.user?.email, purpose: 'password_change' })
    ElMessage.success(data.message || '验证码已模拟投递')
    startCd(pwdCd)
    tab.value = 'inbox'
    loadInbox()
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

async function save() {
  loading.value = true
  try {
    const payload: any = { nickname: form.nickname }
    if (emailChanged.value) {
      payload.email = form.email
      payload.email_code = form.email_code
    }
    if (form.password) {
      payload.password = form.password
      payload.password_code = form.password_code
    }
    await api.put('/api/auth/profile', payload)
    if (auth.user) {
      auth.user.nickname = form.nickname
      auth.user.email = form.email
      localStorage.setItem('spt_user', JSON.stringify(auth.user))
    }
    ElMessage.success('修改成功')
    form.password = ''
    form.email_code = ''
    form.password_code = ''
    loadInbox()
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

// ---------- 我的邮箱 ----------
const inboxLoading = ref(false)
const inbox = reactive({ total: 0, page: 1, page_size: 10, unread: 0, items: [] as any[] })
const mailVisible = ref(false)
const currentMail = ref<any>(null)

function categoryType(c: string) {
  return c === 'verify_code' ? 'warning' : c === 'price_alert' ? 'danger' : c === 'subscribe' ? 'success' : 'info'
}

async function loadInbox(page = 1) {
  inboxLoading.value = true
  try {
    const { data } = await api.get('/api/mail/inbox', { params: { page, page_size: inbox.page_size } })
    inbox.total = data.total
    inbox.page = data.page
    inbox.unread = data.unread
    inbox.items = data.items
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    inboxLoading.value = false
  }
}

async function openMail(row: any) {
  currentMail.value = row
  mailVisible.value = true
  if (!row.is_read) {
    await api.post(`/api/mail/${row.id}/read`)
    row.is_read = true
    inbox.unread = Math.max(0, inbox.unread - 1)
  }
}

async function readAll() {
  await api.post('/api/mail/read-all')
  inbox.items.forEach((m: any) => (m.is_read = true))
  inbox.unread = 0
}

// ---------- 用户画像（AI 自动整理，可手动修改） ----------
const memoContent = ref('')
const memoLoading = ref(false)

async function loadMemo() {
  try {
    const { data } = await api.get('/api/auth/profile-memo')
    memoContent.value = data.content || ''
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

async function saveMemo() {
  if (memoContent.value.length > 20000) {
    ElMessage.warning('画像内容过长（上限 20000 字）')
    return
  }
  memoLoading.value = true
  try {
    await api.put('/api/auth/profile-memo', { content: memoContent.value })
    ElMessage.success('画像已保存，AI 后续建议会参考最新内容')
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    memoLoading.value = false
  }
}

onMounted(() => {
  loadInbox()
  loadMemo()
})

// ================= 标本手记 · 动效（纯表现层，不改动上方业务逻辑） =================
const pageEl = ref<HTMLElement>()
const titleEl = ref<HTMLElement>()
const statsEl = ref<HTMLElement>()
const saveWrap = ref<HTMLElement>()

function runCounts() {
  statsEl.value?.querySelectorAll<HTMLElement>('[data-count]').forEach((el) => countUp(el))
}

// 异步数据到位后：数字滚动 + 刷新滚动触发器
watch(
  () => [inbox.total, inbox.unread],
  () => {
    nextTick(() => {
      runCounts()
      refreshScroll()
    })
  }
)

onMounted(() => {
  splitReveal(titleEl.value ?? null, 0.12)
  revealOnScroll(pageEl.value)
  magnetic(saveWrap.value ?? null)
})
</script>

<style scoped>
.page-head { position: relative; margin-bottom: 16px; }

/* —— 档案速览 —— */
.stat-strip {
  display: flex; padding: 16px 8px; margin-bottom: 18px; max-width: 900px;
}
.stat-strip:hover { transform: none; box-shadow: var(--shadow-md); }
.stat-item {
  flex: 1; text-align: center; padding: 2px 14px;
  border-right: 1px dashed var(--line);
}
.stat-item:last-child { border-right: none; }
.stat-n {
  font-family: var(--mono); font-size: 24px; font-weight: 700;
  color: var(--green); letter-spacing: 0.02em; min-height: 32px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.stat-n.stat-text {
  font-family: var(--serif); font-size: 17px; color: var(--ink); padding-top: 6px;
}
.stat-n.stat-mail { font-family: var(--mono); font-size: 12px; padding-top: 10px; color: var(--ink-soft); }
.stat-l { margin-top: 5px; }

/* —— 资料卡 —— */
.file-card { max-width: 900px; padding: 22px 26px 18px; }
.file-card:hover { transform: none; box-shadow: var(--shadow-md); }

/* —— 用户画像 —— */
.memo-desc { margin: 2px 0 10px; line-height: 1.7; }
.file-card :deep(.el-textarea__inner) {
  font-family: var(--kai); letter-spacing: 0.03em; line-height: 1.8;
}
.memo-foot {
  display: flex; justify-content: space-between; align-items: center; margin-top: 10px;
}
.memo-btns { display: flex; gap: 8px; }
/* —— 透明装饰素材（标本点缀，纯表现层） —— */
.deco { position: absolute; pointer-events: none; user-select: none; z-index: 2; }
.deco-quill {
  width: 105px; right: 12px; top: -6px;
  transform: rotate(5deg); opacity: 0.8;
}
.card-title {
  font-family: var(--serif); font-size: 18px; font-weight: 700;
  letter-spacing: 0.05em; margin: 6px 0 18px; color: var(--ink);
}
.fld {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em;
  color: var(--ink-faint); text-transform: uppercase; white-space: nowrap;
}
.mag-wrap { display: inline-flex; }
.colophon { border-top: 1px dashed var(--line); padding-top: 10px; margin-top: 4px; }

/* —— 信札卡 —— */
.mail-card { padding: 20px 22px; }
.mail-card:hover { transform: none; box-shadow: var(--shadow-md); }
.card-head-row {
  display: flex; justify-content: space-between; align-items: center; margin: 6px 0 12px;
}
.card-head-row .card-title { margin: 0; }

/* —— 标签页 —— */
.profile-tabs { max-width: 900px; }
.profile-tabs :deep(.el-tabs__item) { font-family: var(--serif); letter-spacing: 0.1em; }
</style>
