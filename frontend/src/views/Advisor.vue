<template>
  <div class="page chat-page">
    <div class="card chat-card">
      <!-- 头部 -->
      <div class="chat-head">
        <div class="head-left">
          <el-icon :size="20" color="#409eff"><MagicStick /></el-icon>
          <span class="title">AI 智能导购</span>
          <el-tag size="small" type="success" effect="plain">{{ modelLabel }}</el-tag>
        </div>
        <div class="head-actions">
          <el-button size="small" text @click="settingsVisible = true">
            <el-icon><Setting /></el-icon>&nbsp;模型设置
          </el-button>
          <el-button size="small" text @click="clearChat">清空对话</el-button>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="chat-body" ref="bodyEl">
        <div v-if="!messages.length" class="chat-empty">
          <el-icon :size="42" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p>把商品发给我，帮你分析历史价格、判断购买时机</p>
          <p class="muted">可直接粘贴商品链接 · 选择正在浏览的商品 · 点击下方追踪中的商品</p>
        </div>

        <div v-for="(m, i) in messages" :key="i" :class="['msg-row', m.role]">
          <el-avatar v-if="m.role === 'assistant'" :size="30" class="avatar">
            <el-icon><MagicStick /></el-icon>
          </el-avatar>
          <div :class="['bubble', m.role]">
            <div v-if="m.loading" class="typing">
              <span></span><span></span><span></span>
              <em v-if="m.tip">{{ m.tip }}</em>
            </div>
            <template v-else>
              <!-- 发送的商品：卡片样式 -->
              <div v-if="m.productInfo" class="prod-card">
                <img :src="m.productInfo.image || placeholder" class="pc-img" />
                <div class="pc-info">
                  <div class="pc-name">{{ m.productInfo.name }}</div>
                  <div class="pc-price" v-if="m.productInfo.price">￥{{ m.productInfo.price }}</div>
                </div>
                <el-icon class="pc-arrow" color="#ffffff"><Right /></el-icon>
              </div>
              <div v-if="m.images?.length" class="imgs">
                <img v-for="(u, k) in m.images" :key="k" :src="u" class="msg-img" />
              </div>
              <div v-if="m.files?.length" class="files">
                <a v-for="(f, k) in m.files" :key="k" :href="f.url" target="_blank" class="file-chip">
                  <el-icon><Document /></el-icon>{{ f.name }}
                </a>
              </div>
              <div
                v-if="m.content"
                :class="['content', { md: m.role === 'assistant' }]"
                v-html="m.role === 'assistant' ? renderMd(m.content) : escapeHtml(m.content)"
              ></div>
            </template>
            <div v-if="m.fallback" class="muted" style="margin-top: 4px">⚠ AI 服务降级，展示数据摘要</div>
          </div>
          <el-avatar v-if="m.role === 'user'" :size="30" class="avatar user-avatar">
            {{ avatarText }}
          </el-avatar>
        </div>
      </div>

      <!-- 输入区（微信式：输入框 + 拓展面板） -->
      <div class="input-bar">
        <div class="input-main">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            :placeholder="inputPlaceholder"
            @keydown.enter.exact.prevent="send"
          />
          <div class="btn-col">
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!canSend"
              class="send-btn"
              @click="send"
            >
              发送
            </el-button>
            <el-popover
              placement="top-end"
              :width="300"
              trigger="click"
              v-model:visible="panelVisible"
            >
              <template #reference>
                <el-button class="plus-btn" :circle="!panelVisible" :type="panelVisible ? 'primary' : 'default'">
                  <el-icon :size="18"><component :is="panelVisible ? 'Close' : 'Plus'" /></el-icon>
                </el-button>
              </template>
              <div class="plus-panel">
                <div class="panel-title">发送到对话</div>
                <div class="panel-grid">
                  <div class="panel-item" @click="pickFile('image')">
                    <div class="panel-icon img-icon"><el-icon :size="20"><Picture /></el-icon></div>
                    <span>图片</span>
                  </div>
                  <div class="panel-item" @click="pickFile('file')">
                    <div class="panel-icon file-icon"><el-icon :size="20"><FolderOpened /></el-icon></div>
                    <span>文件</span>
                  </div>
                  <div class="panel-item" @click="showFav = !showFav">
                    <div class="panel-icon fav-icon"><el-icon :size="20"><Star /></el-icon></div>
                    <span>收藏商品</span>
                  </div>
                </div>
                <template v-if="showFav">
                  <div class="panel-title" style="margin-top: 10px">
                    价格追踪（收藏栏）
                    <span class="muted">点击发送</span>
                  </div>
                  <div class="fav-list">
                    <div
                      v-for="t in trackings"
                      :key="t.id"
                      class="fav-item"
                      @click="sendTracking(t)"
                    >
                      <img :src="t.image_url || placeholder" class="fav-img" />
                      <div class="fav-info">
                        <div class="fav-name">{{ shortName(t.product_name, 16) }}</div>
                        <div class="fav-price">
                          <span v-if="t.current_price" class="price">￥{{ t.current_price }}</span>
                          <span v-if="t.target_price" class="muted">目标 ￥{{ t.target_price }}</span>
                        </div>
                      </div>
                      <el-button size="small" type="primary" plain round>发送</el-button>
                    </div>
                    <el-empty v-if="!trackings.length" description="暂无收藏商品" :image-size="50" />
                  </div>
                </template>
              </div>
            </el-popover>
          </div>
        </div>
      </div>

      <!-- 模型设置（配置保存在本机浏览器，支持多套自定义模型） -->
      <el-dialog v-model="settingsVisible" title="AI 模型设置" width="480px">
        <el-radio-group v-model="aiSetting.mode" style="margin-bottom: 12px">
          <el-radio value="default">默认模型</el-radio>
          <el-radio value="custom">自定义模型</el-radio>
        </el-radio-group>
        <template v-if="aiSetting.mode === 'custom'">
          <div style="display: flex; gap: 8px; align-items: center">
            <el-select v-model="editId" placeholder="选择配置" style="flex: 1">
              <el-option
                v-for="c in aiSetting.configs"
                :key="c.id"
                :label="c.name || c.model || '未命名配置'"
                :value="c.id"
              />
            </el-select>
            <el-button size="small" @click="addAiCfg">新增</el-button>
            <el-button size="small" type="danger" plain :disabled="!editingCfg" @click="removeAiCfg">删除</el-button>
          </div>
          <el-form v-if="editingCfg" label-width="90px" style="margin-top: 12px">
            <el-form-item label="名称">
              <el-input v-model="editingCfg.name" placeholder="配置名称，如：我的 GPT" />
            </el-form-item>
            <el-form-item label="API Base">
              <el-input v-model="editingCfg.api_base" placeholder="https://api.openai.com/v1" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="editingCfg.api_key" type="password" show-password placeholder="sk-..." />
            </el-form-item>
            <el-form-item label="Model">
              <el-input v-model="editingCfg.model" placeholder="如 gpt-4o-mini" />
            </el-form-item>
          </el-form>
          <el-empty v-else description="暂无自定义配置，点击新增添加" :image-size="60" />
          <div class="muted" style="font-size: 12px">
            可保存多套 OpenAI 兼容接口配置并随时切换；配置只保存在本机浏览器（localStorage），不会上传服务器
          </div>
        </template>
        <div v-else class="muted" style="font-size: 12px">
          使用服务端配置的默认模型
        </div>
        <template #footer>
          <el-button @click="settingsVisible = false">取消</el-button>
          <el-button type="primary" @click="saveAiCfg">保存</el-button>
        </template>
      </el-dialog>

      <!-- 隐藏的文件选择 -->
      <input
        ref="imgInput"
        type="file"
        accept="image/*"
        multiple
        style="display: none"
        @change="onImagePick"
      />
      <input ref="fileInput" type="file" style="display: none" @change="onFilePick" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'

const route = useRoute()
const auth = useAuthStore()

interface Msg {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  tip?: string
  fallback?: boolean
  images?: string[]
  files?: { name: string; url: string }[]
  productInfo?: { id: number; name: string; price: number | null; image: string }
  raw?: string  // 发送给 AI 的原文（含 [[product:N]] 标记）
}

// 对话历史持久化：切换页面/刷新都保留，仅手动"清空对话"才清除
const CHAT_KEY = 'spt_advisor_chat'
function loadChat(): Msg[] {
  try {
    const saved = sessionStorage.getItem(CHAT_KEY)
    if (saved) {
      const list: Msg[] = JSON.parse(saved)
      // 恢复时重置未完成的加载态
      for (const m of list) {
        if (m.loading) {
          m.loading = false
          m.content = m.content || '（上次对话被中断，请重新发送）'
        }
      }
      return list
    }
  } catch {
    /* 解析失败则开新对话 */
  }
  return []
}

const messages = ref<Msg[]>(loadChat())
watch(
  messages,
  (v) => {
    try {
      sessionStorage.setItem(CHAT_KEY, JSON.stringify(v))
    } catch {
      /* 存储超限忽略 */
    }
  },
  { deep: true }
)
const input = ref('')
const sending = ref(false)
const bodyEl = ref<HTMLDivElement>()
const trackings = ref<any[]>([])
const panelVisible = ref(false)
const showFav = ref(false)
const imgInput = ref<HTMLInputElement>()
const fileInput = ref<HTMLInputElement>()
const pendingImages = ref<string[]>([])  // dataURI
const pendingFiles = ref<{ name: string; url: string }[]>([])

// ---- 模型设置：用户本地配置（localStorage），支持多套自定义模型，仅用于聊天 ----
interface AiModelCfg {
  id: string
  name: string
  api_base: string
  api_key: string
  model: string
}
interface AiSetting {
  mode: 'default' | 'custom'
  activeId: string  // 当前生效的自定义配置 id
  configs: AiModelCfg[]
}
const AI_CFG_KEY = 'spt_ai_setting'
function loadAiSetting(): AiSetting {
  try {
    const raw = localStorage.getItem(AI_CFG_KEY)
    if (raw) {
      const s = JSON.parse(raw)
      const configs: AiModelCfg[] = Array.isArray(s.configs) ? s.configs : []
      return {
        mode: s.mode === 'custom' ? 'custom' : 'default',
        activeId: s.activeId && configs.some((c) => c.id === s.activeId) ? s.activeId : (configs[0]?.id || ''),
        configs,
      }
    }
    // 兼容旧版单配置数据（spt_ai_config）
    const legacy = localStorage.getItem('spt_ai_config')
    if (legacy) {
      const c = JSON.parse(legacy)
      if (c.mode === 'custom' && c.api_base) {
        const cfg: AiModelCfg = {
          id: newCfgId(),
          name: c.model || '自定义模型',
          api_base: c.api_base,
          api_key: c.api_key || '',
          model: c.model || '',
        }
        return { mode: 'custom', activeId: cfg.id, configs: [cfg] }
      }
    }
  } catch {
    /* 解析失败用默认配置 */
  }
  return { mode: 'default', activeId: '', configs: [] }
}
function newCfgId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}
const aiSetting = ref<AiSetting>(loadAiSetting())
const settingsVisible = ref(false)
const editId = ref(aiSetting.value.activeId || aiSetting.value.configs[0]?.id || '')
const editingCfg = computed(() =>
  aiSetting.value.configs.find((c) => c.id === editId.value)
)
const activeCfg = computed(() => {
  const s = aiSetting.value
  return s.configs.find((c) => c.id === s.activeId) || s.configs[0]
})
const modelLabel = computed(() => {
  if (aiSetting.value.mode !== 'custom') return '默认模型'
  return activeCfg.value?.name || activeCfg.value?.model || '自定义模型'
})
function addAiCfg() {
  const cfg: AiModelCfg = { id: newCfgId(), name: '', api_base: '', api_key: '', model: '' }
  aiSetting.value.configs.push(cfg)
  editId.value = cfg.id
}
function removeAiCfg() {
  const s = aiSetting.value
  const idx = s.configs.findIndex((c) => c.id === editId.value)
  if (idx < 0) return
  s.configs.splice(idx, 1)
  editId.value = s.configs[0]?.id || ''
}
function saveAiCfg() {
  const s = aiSetting.value
  if (s.mode === 'custom') {
    const cfg = s.configs.find((c) => c.id === editId.value)
    if (!cfg) {
      ElMessage.warning('请先新增一套自定义配置')
      return
    }
    if (!cfg.api_base.trim() || !cfg.api_key.trim() || !cfg.model.trim()) {
      ElMessage.warning('请填写完整的自定义模型信息')
      return
    }
    if (!cfg.name.trim()) cfg.name = cfg.model.trim()
    s.activeId = cfg.id
  }
  localStorage.setItem(AI_CFG_KEY, JSON.stringify(s))
  settingsVisible.value = false
  ElMessage.success('模型设置已保存')
}
function currentAiConfig() {
  const s = aiSetting.value
  if (s.mode !== 'custom') return null
  const cfg = activeCfg.value
  return cfg
    ? { api_base: cfg.api_base.trim(), api_key: cfg.api_key.trim(), model: cfg.model.trim() }
    : null
}
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20shopping%20bag&image_size=square'

const avatarText = computed(() => (auth.user?.nickname || auth.user?.username || '?').slice(0, 1))
const canSend = computed(() => sending.value || !!(input.value.trim() || pendingImages.value.length || pendingFiles.value.length))
const inputPlaceholder = computed(() =>
  sending.value
    ? 'AI 正在思考…'
    : pendingImages.value.length || pendingFiles.value.length
      ? '可补充说明（选填），回车发送附件…'
      : '输入问题，或粘贴商品链接（会自动抓取历史价格分析）…'
)

function shortName(s: string, n = 10) {
  return s && s.length > n ? s.slice(0, n) + '…' : s || ''
}

function scrollBottom() {
  nextTick(() => {
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
  })
}

// 发送（统一入口，可携带附件）
async function send() {
  if (!canSend.value) return
  const text = input.value.trim()
  const images = [...pendingImages.value]
  const files = [...pendingFiles.value]
  input.value = ''
  pendingImages.value = []
  pendingFiles.value = []
  await pushUser(text || (images.length ? '[图片]' : '[文件]'), undefined, images, files)
}

async function pushUser(text: string, productId?: number, images: string[] = [], files: { name: string; url: string }[] = []) {
  // 解析 [[product:N]] -> 查询商品渲染为卡片，正文只保留问题
  let productInfo: Msg['productInfo']
  const pm = text.match(/\[\[product:(\d+)\]\]/)
  if (pm) {
    try {
      const { data } = await api.get(`/api/products/${pm[1]}`)
      productInfo = { id: data.id, name: data.name, price: data.min_price, image: data.image_url }
    } catch {
      /* 查不到就退回文本展示 */
    }
  }
  const display = text.replace(/\[\[product:\d+\]\]/g, '').trim()

  messages.value.push({
    role: 'user',
    content: display || (productInfo ? '' : '[商品]'),
    raw: text,
    productInfo,
    images: images.length ? images : undefined,
    files: files.length ? files : undefined,
  })
  const tip = /https?:\/\//.test(text)
    ? '正在抓取链接商品的历史价格…'
    : images.length
      ? '正在识别图片…'
      : '正在分析…'
  messages.value.push({ role: 'assistant', content: '', loading: true, tip })
  sending.value = true
  scrollBottom()

  const history = messages.value
    .filter((m) => !m.loading && (m.content || m.raw || m.images?.length))
    .slice(0, -1)
    .map((m) => ({
      role: m.role,
      content: m.raw || m.content || (m.images?.length ? '[图片]' : '[文件]'),
    }))

  try {
    const { data } = await api.post(
      '/api/advisor/chat',
      { message: text, history, product_id: productId ?? null, images, files, ai_config: currentAiConfig() },
      { timeout: 120000 }
    )
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    if (data.ok === false) {
      last.content = '⚠ ' + (data.error || '请求被拒绝')
    } else if (data.blocked) {
      last.content = '⚠ ' + (data.reply || 'AI 回复包含敏感内容，已被拦截')
    } else {
      last.content = data.reply
      last.fallback = data.fallback
    }
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    last.content = '请求失败：' + errMsg(e)
  } finally {
    sending.value = false
    scrollBottom()
  }
}

// ---- + 拓展面板：图片 / 文件 / 收藏商品 ----
function pickFile(kind: 'image' | 'file') {
  panelVisible.value = false
  showFav.value = false
  ;(kind === 'image' ? imgInput : fileInput).value?.click()
}

function onImagePick(e: Event) {
  const el = e.target as HTMLInputElement
  for (const f of Array.from(el.files || [])) {
    if (f.size > 8 * 1024 * 1024) {
      ElMessage.warning(`图片 ${f.name} 超过 8MB，已跳过`)
      continue
    }
    const reader = new FileReader()
    reader.onload = () => pendingImages.value.push(String(reader.result))
    reader.readAsDataURL(f)
  }
  el.value = ''
}

async function onFilePick(e: Event) {
  const el = e.target as HTMLInputElement
  for (const f of Array.from(el.files || [])) {
    const fd = new FormData()
    fd.append('file', f)
    try {
      const { data } = await api.post('/api/advisor/upload', fd, { timeout: 60000 })
      pendingFiles.value.push({ name: data.name, url: data.url })
    } catch (err) {
      ElMessage.error(`上传失败：${errMsg(err)}`)
    }
  }
  el.value = ''
}

// Markdown 渲染（AI 回复）与转义（用户文本）
function renderMd(s: string) {
  try {
    const html = marked.parse(s, { async: false }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return escapeHtml(s)
  }
}
function escapeHtml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

// 价格追踪（收藏栏）商品发送
function sendTracking(t: any) {
  if (sending.value) return
  panelVisible.value = false
  showFav.value = false
  pushUser(`[[product:${t.product_id}]] 这个商品现在值得买吗？`)
}

async function loadTrackings() {
  try {
    const { data } = await api.get('/api/tracking')
    trackings.value = data
  } catch {
    /* 未登录等情况忽略 */
  }
}

function clearChat() {
  // 手动清除：清空记录并移除持久化存档
  messages.value = []
  sessionStorage.removeItem(CHAT_KEY)
}

onMounted(async () => {
  // 仅首次（无历史）显示欢迎语
  if (!messages.value.length) {
    messages.value.push({
      role: 'assistant',
      content:
        '你好，我是 AI 智能导购。\n' +
        '· 发送商品链接，我会抓取它的历史价格帮你分析\n' +
        '· 点击右侧 + → 收藏商品，把价格追踪的商品发给我\n' +
        '· 也可以直接问我什么时候买最划算',
    })
  } else {
    scrollBottom()
  }
  loadTrackings()
  // 详情页跳转过来的商品（?product=N & ?q=问题）自动发送
  const pid = Number(route.query.product)
  const q = String(route.query.q || '').trim()
  if (pid) {
    const { data } = await api.get(`/api/products/${pid}`).catch(() => ({ data: null }))
    const name = data?.name || `商品 #${pid}`
    const question = q || '帮我分析一下这个商品'
    await pushUser(`[[product:${pid}]] ${question}`, pid)
    void name
  }
})
</script>

<style scoped>
.chat-page { padding: 16px 20px; height: calc(100vh - 60px); display: flex; }
.chat-card {
  flex: 1; display: flex; flex-direction: column; padding: 0; overflow: hidden;
  max-width: 1000px; margin: 0 auto; height: 100%;
}
.chat-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid #ebeef5;
}
.head-left { display: flex; align-items: center; gap: 8px; }
.title { font-weight: 700; font-size: 15px; }
.chat-body { flex: 1; overflow-y: auto; padding: 16px; background: #f7f9fc; }
.chat-empty { text-align: center; color: #909399; margin-top: 80px; }
.chat-empty p { margin: 10px 0 4px; font-size: 14px; }

.msg-row { display: flex; margin-bottom: 14px; gap: 8px; align-items: flex-start; }
.msg-row.user { justify-content: flex-end; }
.avatar { flex-shrink: 0; background: #409eff; color: #fff; }
.user-avatar { background: #67c23a; }
.bubble {
  max-width: 72%; padding: 10px 14px; border-radius: 10px;
  font-size: 14px; line-height: 1.7; word-break: break-word;
}
.bubble.assistant { background: #fff; border: 1px solid #ebeef5; border-top-left-radius: 3px; }
.bubble.user { background: #409eff; color: #fff; border-top-right-radius: 3px; }
.content { white-space: pre-wrap; }

/* 发送的商品卡片 */
.prod-card {
  display: flex; align-items: center; gap: 10px; padding: 8px;
  background: rgba(255, 255, 255, 0.95); border-radius: 8px;
  margin-bottom: 8px; min-width: 240px; max-width: 340px;
}
.pc-img { width: 46px; height: 46px; object-fit: contain; background: #fafafa; border-radius: 6px; flex-shrink: 0; }
.pc-info { flex: 1; min-width: 0; }
.pc-name {
  font-size: 13px; color: #303133; line-height: 1.4; font-weight: 600;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.pc-price { font-size: 14px; color: #f56c6c; font-weight: 700; margin-top: 2px; }
.pc-arrow { flex-shrink: 0; opacity: 0.7; }

/* AI 回复 Markdown 排版 */
.content.md { white-space: normal; }
.md :deep(h1), .md :deep(h2), .md :deep(h3), .md :deep(h4) {
  margin: 12px 0 6px; font-weight: 700; color: #1f2d3d; line-height: 1.4;
}
.md :deep(h1) { font-size: 17px; }
.md :deep(h2) { font-size: 16px; border-bottom: 1px solid #ebeef5; padding-bottom: 4px; }
.md :deep(h3) { font-size: 15px; }
.md :deep(h4) { font-size: 14px; }
.md :deep(p) { margin: 6px 0; line-height: 1.75; }
.md :deep(ul), .md :deep(ol) { margin: 6px 0; padding-left: 20px; }
.md :deep(li) { margin: 3px 0; line-height: 1.7; }
.md :deep(strong) { color: #1f2d3d; }
.md :deep(a) { color: #409eff; }
.md :deep(code) {
  background: #f0f2f5; padding: 1px 5px; border-radius: 4px;
  font-size: 13px; font-family: Consolas, Monaco, monospace;
}
.md :deep(pre) {
  background: #f0f2f5; padding: 10px; border-radius: 6px; overflow-x: auto;
}
.md :deep(pre code) { background: none; padding: 0; }
.md :deep(hr) { border: none; border-top: 1px solid #ebeef5; margin: 10px 0; }
.md :deep(blockquote) {
  border-left: 3px solid #409eff; margin: 8px 0; padding: 4px 12px;
  color: #909399; background: #f7f9fc;
}
.md :deep(table) {
  border-collapse: collapse; margin: 8px 0; font-size: 13px; width: 100%;
}
.md :deep(th), .md :deep(td) {
  border: 1px solid #ebeef5; padding: 6px 10px; text-align: left;
}
.md :deep(th) { background: #f5f7fa; font-weight: 600; }
.md :deep(img) { max-width: 100%; border-radius: 6px; }
.imgs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.msg-img { max-width: 200px; max-height: 160px; border-radius: 6px; border: 1px solid #ebeef5; }
.files { margin-bottom: 6px; }
.file-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px;
  background: #f0f2f5; border-radius: 6px; font-size: 13px; color: #409eff;
  text-decoration: none; margin: 2px 4px 2px 0;
}
.file-chip:hover { background: #e4e7ed; }

.typing { display: flex; align-items: center; gap: 5px; height: 22px; }
.typing span {
  width: 7px; height: 7px; border-radius: 50%; background: #c0c4cc;
  animation: blink 1.2s infinite both;
}
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }
.typing em { font-style: normal; color: #909399; font-size: 12px; margin-left: 6px; }
@keyframes blink { 0%, 80%, 100% { opacity: .3; } 40% { opacity: 1; } }

.input-bar { padding: 12px 16px; background: #fff; border-top: 1px solid #ebeef5; }
.input-main { display: flex; gap: 10px; align-items: flex-end; }
.input-main .el-input { flex: 1; }
.btn-col { display: flex; gap: 8px; align-items: center; }
.plus-btn { flex-shrink: 0; }
.send-btn { width: 88px; }

.plus-panel { max-height: 380px; overflow-y: auto; }
.panel-title { font-size: 13px; color: #909399; margin-bottom: 10px; font-weight: 600; }
.panel-grid { display: flex; gap: 18px; }
.panel-item {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  cursor: pointer; font-size: 12px; color: #606266;
}
.panel-item:hover { color: #409eff; }
.panel-icon {
  width: 52px; height: 52px; border-radius: 10px; display: flex;
  align-items: center; justify-content: center; background: #f0f2f5; color: #606266;
}
.panel-item:hover .panel-icon { background: #ecf5ff; color: #409eff; }
.img-icon { background: #ecf5ff; color: #409eff; }
.file-icon { background: #f0f9eb; color: #67c23a; }
.fav-icon { background: #fdf6ec; color: #e6a23c; }

.fav-list { max-height: 220px; overflow-y: auto; }
.fav-item {
  display: flex; align-items: center; gap: 10px; padding: 8px;
  border-radius: 8px; cursor: pointer; transition: background .15s;
}
.fav-item:hover { background: #f5f7fa; }
.fav-img { width: 40px; height: 40px; object-fit: contain; background: #fafafa; border-radius: 6px; flex-shrink: 0; }
.fav-info { flex: 1; min-width: 0; }
.fav-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fav-price { font-size: 12px; display: flex; gap: 8px; margin-top: 2px; }
</style>
