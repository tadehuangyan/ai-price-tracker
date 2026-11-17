<template>
  <div class="login-page">
    <!-- ============ 背景层：邮戳档案 ============ -->
    <div class="login-bg" aria-hidden="true">
      <div class="bg-frame" ref="bgFrameRef"></div>
      <div class="bg-cross c-tl"></div>
      <div class="bg-cross c-tr"></div>
      <div class="bg-cross c-bl"></div>
      <div class="bg-cross c-br"></div>
      <div class="bg-postmark pm-1" ref="pm1Ref">
        <b>ARCHIVE</b><span>PRICE SPECIMEN · 2026</span><i class="wave"></i>
      </div>
      <div class="bg-postmark pm-2" ref="pm2Ref">
        <b>COLLECTED</b><span>PRICETRACE</span><i class="wave"></i>
      </div>
      <div class="bg-stamp st-1" ref="st1Ref">RECEIVED · 已入藏</div>
      <div class="bg-stamp st-2" ref="st2Ref">CASE FILE · 001</div>
    </div>

    <div class="login-grid">
      <!-- ============ 左：标本大铭牌 ============ -->
      <aside class="login-plate">
        <img class="deco deco-seal" src="/deco/wax-seal.png" alt="" aria-hidden="true" />
        <img class="deco deco-fern" src="/deco/fern-sprig.png" alt="" aria-hidden="true" />
        <span class="tape plate-tape-l"></span>
        <span class="tape plate-tape-r"></span>
        <span class="pin plate-pin" ref="pinRef"></span>

        <div class="kicker"><span class="pin-dot"></span>SPECIMEN ARCHIVE · 标本馆</div>
        <h1 class="plate-title">
          <span class="plate-cn" ref="titleRef">价迹</span>
          <span class="plate-en">PRICETRACE</span>
        </h1>
        <p class="plate-lead annot">
          凡物有价，皆可入藏。<br />
          记录每一次涨落，如压制一枚标本，<br />
          待日后来查。
        </p>
        <div class="plate-annot lead-line annot">此册为商品历史价格追踪系统，登记后可取阅全部标本。</div>
        <div class="plate-foot colophon">SPECIMEN No.001 · CASE FILE · EST. 2026</div>
      </aside>

      <!-- ============ 右：入馆登记卡 ============ -->
      <section class="login-card spec-card" ref="cardRef">
        <img class="deco deco-washi" src="/deco/washi-tape.png" alt="" aria-hidden="true" />
        <div class="card-head">
          <div class="kicker"><span class="pin-dot"></span>SPECIMEN REGISTRY</div>
          <h2 class="card-title">入馆登记</h2>
        </div>

        <el-tabs v-model="tab">
          <el-tab-pane label="登录" name="login">
            <el-form :model="loginForm" @submit.prevent="doLogin">
              <el-form-item>
                <div class="field-label kicker">USER NAME · 用户名</div>
                <el-input v-model="loginForm.username" placeholder="用户名或邮箱" size="large">
                  <template #prefix><el-icon><User /></el-icon></template>
                </el-input>
              </el-form-item>
              <el-form-item>
                <div class="field-label kicker">PASSKEY · 密码</div>
                <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="doLogin">
                  <template #prefix><el-icon><Lock /></el-icon></template>
                </el-input>
              </el-form-item>
              <div class="submit-wrap" ref="loginBtnRef">
                <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doLogin">登 录</el-button>
              </div>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="注册" name="register">
            <el-form :model="regForm" @submit.prevent="doRegister">
              <el-form-item>
                <div class="field-label kicker">USER NAME · 用户名</div>
                <el-input v-model="regForm.username" placeholder="用户名（3~20 位字母数字下划线）" size="large" />
              </el-form-item>
              <el-form-item>
                <div class="field-label kicker">E-MAIL · 邮箱</div>
                <el-input v-model="regForm.email" placeholder="邮箱" size="large" />
              </el-form-item>
              <el-form-item>
                <div class="field-label kicker">CODE · 验证码</div>
                <div style="display: flex; gap: 8px; width: 100%">
                  <el-input v-model="regForm.code" placeholder="6 位验证码" size="large" maxlength="6" />
                  <div class="code-wrap" ref="codeBtnRef">
                    <el-button size="large" :disabled="codeCountdown > 0" @click="sendCode">
                      {{ codeCountdown > 0 ? `${codeCountdown}s 后重发` : '发送验证码' }}
                    </el-button>
                  </div>
                </div>
              </el-form-item>
              <el-form-item>
                <div class="field-label kicker">ALIAS · 昵称</div>
                <el-input v-model="regForm.nickname" placeholder="昵称（选填）" size="large" />
              </el-form-item>
              <el-form-item>
                <div class="field-label kicker">PASSKEY · 密码</div>
                <el-input v-model="regForm.password" type="password" placeholder="密码（>=8 位，含字母和数字）" size="large" show-password />
              </el-form-item>
              <div class="submit-wrap" ref="regBtnRef">
                <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doRegister">注 册</el-button>
              </div>
            </el-form>
            <div class="muted" style="margin-top: 8px; text-align: center">
              邮件为<el-link type="primary" :underline="false" @click="openSandbox">沙箱模拟投递</el-link>，验证码请到模拟收件箱查看
            </div>
          </el-tab-pane>
        </el-tabs>
        <div class="card-foot annot">管理员账号：admin / admin123456</div>
      </section>
    </div>

    <el-dialog v-model="sandboxVisible" title="模拟收件箱（沙箱）" width="560px">
      <div class="muted" style="margin-bottom: 10px">
        SMTP 端口受限，系统邮件不真实外发，而是模拟投递到沙箱收件箱（类比支付宝沙箱）。当前查询：{{ regForm.email || '（请先填写邮箱）' }}
      </div>
      <el-table :data="sandboxMails" size="small" v-loading="sandboxLoading" empty-text="暂无模拟邮件">
        <el-table-column prop="created_at" label="时间" width="150" />
        <el-table-column prop="subject" label="主题" show-overflow-tooltip />
        <el-table-column label="验证码" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.code" size="small" type="warning">{{ row.code }}</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 12px" v-if="sandboxMails.length">
        <div v-for="m in sandboxMails.slice(0, 3)" :key="m.id" class="muted" style="white-space: pre-wrap; font-size: 12px">{{ m.body }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { gsap } from 'gsap'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'
import { splitReveal, popIn, pinPress, magnetic, reducedMotion } from '../anim'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '', remember: true })
const regForm = reactive({ username: '', password: '', email: '', nickname: '', code: '' })

// 模拟邮箱（沙箱）
const codeCountdown = ref(0)
let countdownTimer: any = null
const sandboxVisible = ref(false)
const sandboxLoading = ref(false)
const sandboxMails = ref<any[]>([])

function startCountdown() {
  codeCountdown.value = 60
  countdownTimer && clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    codeCountdown.value--
    if (codeCountdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
}

async function sendCode() {
  if (!regForm.email) return ElMessage.warning('请先填写邮箱')
  try {
    const { data } = await api.post('/api/mail/send-code', { email: regForm.email, purpose: 'register' })
    ElMessage.success(data.message || '验证码已模拟投递')
    startCountdown()
    openSandbox()
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

async function openSandbox() {
  if (!regForm.email) return ElMessage.warning('请先填写邮箱')
  sandboxVisible.value = true
  sandboxLoading.value = true
  try {
    const { data } = await api.get('/api/mail/sandbox', { params: { email: regForm.email } })
    sandboxMails.value = data.items || []
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    sandboxLoading.value = false
  }
}

async function doLogin() {
  loading.value = true
  try {
    const { data } = await api.post('/api/auth/login', loginForm)
    auth.login(data.token, data.user)
    ElMessage.success('登录成功')
    router.push(data.role === 'admin' ? '/admin' : '/')
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  if (!regForm.code) return ElMessage.warning('请填写邮箱验证码')
  loading.value = true
  try {
    await api.post('/api/auth/register', regForm)
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    loginForm.username = regForm.username
    loginForm.password = regForm.password
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

/* ================= 动效编排（仅动效，不涉及业务逻辑） ================= */
const titleRef = ref<HTMLElement | null>(null)
const cardRef = ref<HTMLElement | null>(null)
const pinRef = ref<HTMLElement | null>(null)
const loginBtnRef = ref<HTMLElement | null>(null)
const regBtnRef = ref<HTMLElement | null>(null)
const codeBtnRef = ref<HTMLElement | null>(null)
const bgFrameRef = ref<HTMLElement | null>(null)
const pm1Ref = ref<HTMLElement | null>(null)
const pm2Ref = ref<HTMLElement | null>(null)
const st1Ref = ref<HTMLElement | null>(null)
const st2Ref = ref<HTMLElement | null>(null)

onMounted(() => {
  splitReveal(titleRef.value)
  popIn(cardRef.value, 0.15)
  pinPress(pinRef.value, 0.8)
  magnetic(loginBtnRef.value)
  magnetic(regBtnRef.value)
  magnetic(codeBtnRef.value)

  // 背景「邮戳档案」：逐枚盖章式入场（reducedMotion 时 anim.ts 直出终态）
  if (!reducedMotion && gsap) {
    const stamps = [pm1Ref.value, pm2Ref.value, st1Ref.value, st2Ref.value].filter(Boolean)
    gsap.from(bgFrameRef.value, { opacity: 0, duration: 0.6, delay: 0.1 })
    gsap.from(stamps, {
      opacity: 0,
      scale: 1.3,
      rotation: (i: number) => [-18, 15, 8, -10][i] ?? 0,
      duration: 0.5,
      ease: 'back.out(1.7)',
      stagger: 0.12,
      delay: 0.35,
    })
    gsap.from('.bg-cross', { opacity: 0, duration: 0.5, delay: 0.9 })
  }
})

onUnmounted(() => {
  const els = [
    titleRef.value, cardRef.value, pinRef.value, loginBtnRef.value, regBtnRef.value, codeBtnRef.value,
    bgFrameRef.value, pm1Ref.value, pm2Ref.value, st1Ref.value, st2Ref.value,
  ].filter((el): el is HTMLElement => !!el)
  gsap.killTweensOf(els)
  gsap.killTweensOf('.bg-cross')
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  /* 横线档案纸 */
  background-image: repeating-linear-gradient(
    0deg,
    transparent 0 27px,
    rgba(60, 90, 69, 0.06) 27px 28px
  );
}

/* —— 背景层：邮戳档案 —— */
.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.bg-frame {
  position: absolute;
  inset: 22px;
  border: 2px solid rgba(60, 90, 69, 0.22);
}
.bg-frame::before {
  content: "";
  position: absolute;
  inset: 5px;
  border: 1px dashed rgba(60, 90, 69, 0.25);
}
.bg-cross {
  position: absolute;
  width: 15px;
  height: 15px;
}
.bg-cross::before,
.bg-cross::after {
  content: "";
  position: absolute;
  background: rgba(60, 90, 69, 0.4);
}
.bg-cross::before {
  width: 15px;
  height: 1px;
  top: 7px;
}
.bg-cross::after {
  width: 1px;
  height: 15px;
  left: 7px;
}
.c-tl { left: 44px; top: 44px; }
.c-tr { right: 44px; top: 44px; }
.c-bl { left: 44px; bottom: 44px; }
.c-br { right: 44px; bottom: 44px; }

.bg-postmark {
  position: absolute;
  width: 132px;
  height: 132px;
  border: 2.5px double rgba(60, 90, 69, 0.4);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  color: rgba(60, 90, 69, 0.5);
  letter-spacing: 0.14em;
}
.bg-postmark b {
  font-size: 12px;
  letter-spacing: 0.3em;
}
.bg-postmark span {
  font-size: 8px;
  margin-top: 3px;
}
.bg-postmark .wave {
  width: 86px;
  height: 10px;
  margin-top: 5px;
  background: repeating-linear-gradient(90deg, rgba(60, 90, 69, 0.4) 0 7px, transparent 7px 11px);
}
.pm-1 {
  left: 6%;
  top: 12%;
  transform: rotate(-12deg);
}
.pm-2 {
  right: 7%;
  bottom: 14%;
  width: 108px;
  height: 108px;
  transform: rotate(9deg);
}
.pm-2 .wave { width: 66px; }

.bg-stamp {
  position: absolute;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.26em;
  color: rgba(185, 59, 38, 0.55);
  border: 1.5px solid rgba(185, 59, 38, 0.4);
  padding: 6px 12px;
}
.st-1 {
  right: 12%;
  top: 10%;
  transform: rotate(3deg);
}
.st-2 {
  left: 9%;
  bottom: 11%;
  transform: rotate(-5deg);
}
.login-grid {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: 1.1fr 430px;
  gap: 56px;
  align-items: center;
}

/* —— 左：大铭牌 —— */
.login-plate {
  position: relative;
  padding: 52px 46px 44px;
  background: rgba(251, 248, 239, 0.55);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
}
.login-plate::before {
  content: "";
  position: absolute;
  inset: 6px;
  border: 1px solid rgba(185, 170, 142, 0.32);
  border-radius: 2px;
  pointer-events: none;
}
.plate-tape-l {
  top: -11px;
  left: 34px;
  transform: rotate(-5deg);
}
.plate-tape-r {
  top: -11px;
  right: 34px;
  transform: rotate(4deg);
}
.plate-pin {
  top: 22px;
  right: 26px;
}
.plate-title {
  margin: 16px 0 0;
  display: flex;
  align-items: baseline;
  gap: 16px;
  line-height: 1.1;
}
.plate-cn {
  font-family: var(--serif);
  font-size: 68px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--ink);
}
.plate-en {
  font-family: var(--mono);
  font-size: 15px;
  letter-spacing: 0.32em;
  color: var(--pin);
}
.plate-lead {
  margin: 26px 0 0;
  font-size: 15px;
  line-height: 2.1;
  letter-spacing: 0.12em;
}
.plate-annot {
  margin-top: 22px;
  font-size: 12.5px;
  letter-spacing: 0.1em;
}
.plate-foot {
  margin-top: 34px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
}
/* —— 透明装饰素材 —— */
.deco {
  position: absolute;
  pointer-events: none;
  user-select: none;
  z-index: 1;
}
.deco-seal {
  z-index: 5; /* 火漆章是「盖上去」的，压在胶带之上 */
  top: -20px;
  right: -18px;
  width: 86px;
  transform: rotate(-10deg);
  opacity: 0.92;
}
.deco-fern {
  right: -22px;
  bottom: -16px;
  width: 122px;
  transform: rotate(11deg);
  opacity: 0.8;
}
.deco-washi {
  top: -14px;
  right: -12px;
  width: 140px;
  transform: rotate(-4deg);
}

/* —— 右：登记卡 —— */
.login-card {
  padding: 32px 32px 24px;
}
.card-head {
  margin-bottom: 6px;
}
.card-title {
  margin: 7px 0 14px;
  font-family: var(--serif);
  font-size: 23px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--ink);
}
.field-label {
  margin-bottom: 6px;
}
.submit-wrap {
  width: 100%;
  margin-top: 4px;
}
.code-wrap {
  flex: none;
}
.card-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
  font-size: 12px;
  text-align: center;
}

@media (max-width: 1280px) {
  .login-grid {
    gap: 36px;
    grid-template-columns: 1fr 410px;
  }
  .plate-cn {
    font-size: 56px;
  }
  .login-plate {
    padding: 44px 36px 38px;
  }
  .deco-seal {
    width: 76px;
  }
  .deco-fern {
    width: 104px;
  }
  .deco-washi {
    width: 124px;
  }
}
</style>
