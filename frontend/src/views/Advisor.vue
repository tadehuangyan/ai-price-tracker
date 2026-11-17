<template>
  <div class="page chat-page">
    <div class="card chat-card spec-card">
      <!-- 头部：研究员手记 -->
      <div class="chat-head">
        <img src="/deco/butterfly.png" alt="" aria-hidden="true" class="deco deco-butterfly" />
        <div class="head-left">
          <span class="pin head-pin" ref="headPin"></span>
          <div class="head-text">
            <div class="kicker"><span class="pin-dot"></span>RESEARCH NOTES · 研究员手记</div>
            <span class="title" ref="titleEl">AI 智能导购</span>
          </div>
          <span class="model-tag">{{ modelLabel }}</span>
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
          <img src="/deco/fern-sprig.png" alt="" aria-hidden="true" class="deco deco-fern" />
          <div class="kicker"><span class="pin-dot"></span>NEW PLATE · 新的一页</div>
          <el-icon :size="42" color="#b9aa8e"><ChatDotRound /></el-icon>
          <p class="lead-text">把商品发给我，帮你分析历史价格、判断购买时机</p>
          <p class="muted">可直接粘贴商品链接 · 选择正在浏览的商品 · 点击下方追踪中的商品</p>
        </div>

        <div v-for="(m, i) in messages" :key="i" :class="['msg-row', m.role]">
          <div v-if="m.role === 'assistant'" class="avatar ai-avatar">AI</div>
          <div :class="['bubble', m.role]">
            <span v-if="m.role === 'user'" class="tape note-tape"></span>
            <div v-if="m.loading" class="typing">
              <span class="rec-label">记录中</span>
              <span class="pen-dot"></span><span class="pen-dot"></span><span class="pen-dot"></span>
              <em v-if="m.tip">{{ m.tip }}</em>
            </div>
            <template v-else>
              <!-- 发送的商品：标本铭牌 -->
              <div v-if="m.productInfo" class="prod-card">
                <div class="pc-frame">
                  <img :src="m.productInfo.image || placeholder" class="pc-img" />
                </div>
                <div class="pc-info">
                  <div class="pc-no">SPECIMEN NO.{{ String(m.productInfo.id).padStart(4, '0') }}</div>
                  <div class="pc-name">{{ m.productInfo.name }}</div>
                  <div class="pc-price price" v-if="m.productInfo.price">￥{{ m.productInfo.price }}</div>
                  <div class="pc-price muted" v-else>暂无报价</div>
                </div>
                <el-icon class="pc-arrow"><Right /></el-icon>
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
                v-if="m.content || m.typing"
                :class="['content', { md: m.role === 'assistant' }]"
                v-html="m.role === 'assistant' ? renderMd(m.typing ? m.content + CURSOR_HTML : m.content) : escapeHtml(m.content)"
              ></div>
            </template>
            <div v-if="m.fallback" class="muted" style="margin-top: 4px">⚠ AI 服务降级，展示数据摘要</div>
          </div>
          <el-avatar v-if="m.role === 'user'" :size="30" class="avatar user-avatar">
            {{ avatarText }}
          </el-avatar>
        </div>
      </div>

      <!-- 输入区：观察记录纸 -->
      <div class="input-bar">
        <div class="kicker input-head"><span class="pin-dot"></span>FIELD NOTES · 观察记录纸</div>
        <!-- 粘贴/选择的附件预览 -->
        <div v-if="pendingImages.length || pendingFiles.length" class="pending-row">
          <div v-for="(u, k) in pendingImages" :key="'pi' + k" class="pending-item">
            <img :src="u" class="pending-thumb" />
            <span class="pend-del" title="移除" @click="pendingImages.splice(k, 1)">×</span>
          </div>
          <div v-for="(f, k) in pendingFiles" :key="'pf' + k" class="pending-item pending-doc">
            <el-icon><Document /></el-icon>
            <span class="pend-name">{{ shortName(f.name, 14) }}</span>
            <span class="pend-del" title="移除" @click="pendingFiles.splice(k, 1)">×</span>
          </div>
        </div>
        <div class="input-main">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            :placeholder="inputPlaceholder"
            @paste="onPaste"
            @keydown.enter.exact.prevent="send"
          />
          <div class="btn-col">
            <span class="send-wrap" ref="sendWrap">
              <el-button
                type="primary"
                :loading="sending"
                :disabled="!canSend"
                class="send-btn"
                @click="send"
              >
                发送
              </el-button>
            </span>
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
                <div class="panel-title">标本工具箱 · 发送到对话</div>
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
        <div class="ai-settings">
          <div class="kicker anim-item"><span class="pin-dot"></span>MODEL REGISTRY · 模型登记</div>
          <el-radio-group v-model="aiSetting.mode" class="anim-item" style="margin: 6px 0 12px">
            <el-radio value="default">默认模型</el-radio>
            <el-radio value="custom">自定义模型</el-radio>
          </el-radio-group>
          <template v-if="aiSetting.mode === 'custom'">
            <div class="cfg-specimen anim-item">
              <div class="kicker"><span class="pin-dot"></span>CONFIG SPECIMEN · 配置标本</div>
              <div style="display: flex; gap: 8px; align-items: center; margin-top: 8px">
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
            </div>
            <el-form v-if="editingCfg" label-width="110px" class="anim-item" style="margin-top: 12px">
              <el-form-item>
                <template #label><span class="fld">NAME · 名称</span></template>
                <el-input v-model="editingCfg.name" placeholder="配置名称，如：我的 GPT" />
              </el-form-item>
              <el-form-item>
                <template #label><span class="fld">API BASE</span></template>
                <el-input v-model="editingCfg!.api_base" placeholder="https://api.openai.com/v1" />
              </el-form-item>
              <el-form-item>
                <template #label><span class="fld">API KEY</span></template>
                <el-input v-model="editingCfg!.api_key" type="password" show-password placeholder="sk-..." />
              </el-form-item>
              <el-form-item>
                <template #label><span class="fld">MODEL</span></template>
                <el-input v-model="editingCfg!.model" placeholder="如 gpt-4o-mini" />
              </el-form-item>
            </el-form>
            <el-empty v-else description="暂无自定义配置，点击新增添加" :image-size="60" />
            <div class="muted anim-item" style="font-size: 12px">
              可保存多套 OpenAI 兼容接口配置并随时切换；配置只保存在本机浏览器（localStorage），不会上传服务器
            </div>
          </template>
          <div v-else class="muted anim-item" style="font-size: 12px">
            使用服务端配置的默认模型
          </div>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'
import { magnetic, pinPress, popIn, refreshScroll, splitReveal } from '../anim'

const route = useRoute()
const auth = useAuthStore()

interface Msg {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  typing?: boolean  // 打字机逐字输出中
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
      // 恢复时重置未完成的加载/打字态
      for (const m of list) {
        if (m.loading || m.typing) {
          m.loading = false
          m.typing = false
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
      : '输入问题、粘贴商品链接或粘贴图片/文件（自动抓取历史价格分析）…'
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
  if (!canSend.value || sending.value) return
  const text = input.value.trim()
  const images = [...pendingImages.value]
  const files = [...pendingFiles.value]
  const ok = await pushUser(text || (images.length ? '[图片]' : '[文件]'), undefined, images, files)
  if (ok) {
    input.value = ''
    pendingImages.value = []
    pendingFiles.value = []
  } else {
    // 违规拦截：恢复输入内容供修改
    input.value = text
    pendingImages.value = images
    pendingFiles.value = files
  }
}

// 流式读取 AI 回复（SSE）：边生成边渲染；输出违规时服务端中断并替换为违规提示
async function streamChat(
  payload: any,
  onDelta: (text: string) => void
): Promise<{ blocked?: boolean; reply?: string; fallback?: boolean; error?: string; ok?: boolean }> {
  const res = await fetch('/api/advisor/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('spt_token') || ''}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok || !res.body) {
    let detail = ''
    try {
      const j = await res.json()
      detail = j.error || j.detail || ''
    } catch {
      /* 非 JSON 错误体 */
    }
    return { ok: false, error: detail || `请求失败（${res.status}）` }
  }
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('text/event-stream')) {
    // 开流前的 JSON 错误（输入敏感词 / 配置不完整）
    return await res.json()
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  const result: { blocked?: boolean; reply?: string; fallback?: boolean; error?: string } = {}
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx).trim()
      buf = buf.slice(idx + 2)
      if (!raw.startsWith('data:')) continue
      let ev: any
      try {
        ev = JSON.parse(raw.slice(5).trim())
      } catch {
        continue
      }
      if (ev.type === 'delta') onDelta(ev.text || '')
      else if (ev.type === 'blocked') {
        result.blocked = true
        result.reply = ev.reply
      } else if (ev.type === 'done') result.fallback = ev.fallback
      else if (ev.type === 'error') result.error = ev.message || '生成中断'
    }
  }
  return result
}

async function pushUser(
  text: string,
  productId?: number,
  images: string[] = [],
  files: { name: string; url: string }[] = []
): Promise<boolean> {
  // 发送前敏感词预检：命中则弹窗拦截，不进入对话（REQ 违规不入对话）
  try {
    const { data } = await api.post('/api/advisor/check', { text })
    if (data.blocked) {
      ElMessageBox.alert(
        `消息包含敏感词：${(data.hits || []).join('、')}，请修改后重新发送`,
        '内容违规拦截',
        { type: 'warning', confirmButtonText: '去修改' }
      )
      return false
    }
  } catch {
    /* 预检接口异常时放行，后端 chat 仍有兜底拦截 */
  }

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
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    last.typing = true // 流式输出中：内容区末尾显示光标
    last.content = ''
    // 增量渲染节流，避免每个 chunk 全量重渲染 Markdown
    let pendingText = ''
    let lastRender = 0
    const flush = () => {
      if (!pendingText) return
      last.content += pendingText
      pendingText = ''
      lastRender = Date.now()
      scrollBottom()
    }
    const r = await streamChat(
      { message: text, history, product_id: productId ?? null, images, files, ai_config: currentAiConfig() },
      (t) => {
        pendingText += t
        if (Date.now() - lastRender >= 80) flush()
      }
    )
    flush()
    if (r.blocked) {
      // AI 回复违规：整条回复替换为违规提示
      last.content = '⚠ ' + (r.reply || 'AI 回复包含敏感内容，已被拦截')
    } else if (r.ok === false) {
      if (/敏感词/.test(r.error || '')) {
        // 兜底：敏感词不进入对话，弹窗提示
        messages.value.splice(-2, 2)
        ElMessageBox.alert(r.error, '内容违规拦截', {
          type: 'warning',
          confirmButtonText: '去修改',
        })
        return false
      }
      last.content = '⚠ ' + (r.error || '请求被拒绝')
    } else if (r.error) {
      last.content += (last.content ? '\n\n' : '') + '⚠ 生成中断：' + r.error
    } else {
      last.fallback = r.fallback
    }
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    last.content += (last.content ? '\n\n' : '') + '⚠ 请求失败：' + errMsg(e)
  } finally {
    const last = messages.value[messages.value.length - 1]
    if (last) last.typing = false
    sending.value = false
    scrollBottom()
  }
  return true
}

// ---- + 拓展面板：图片 / 文件 / 收藏商品 ----
function pickFile(kind: 'image' | 'file') {
  panelVisible.value = false
  showFav.value = false
  ;(kind === 'image' ? imgInput : fileInput).value?.click()
}

function readDataURL(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(f)
  })
}

async function addPendingFile(f: File) {
  const fd = new FormData()
  fd.append('file', f)
  const { data } = await api.post('/api/advisor/upload', fd, { timeout: 60000 })
  pendingFiles.value.push({ name: data.name, url: data.url })
}

function onImagePick(e: Event) {
  const el = e.target as HTMLInputElement
  for (const f of Array.from(el.files || [])) {
    addPendingImage(f)
  }
  el.value = ''
}

function addPendingImage(f: File) {
  if (f.size > 8 * 1024 * 1024) {
    ElMessage.warning(`图片 ${f.name || '剪贴板图片'} 超过 8MB，已跳过`)
    return Promise.resolve()
  }
  return readDataURL(f).then((url) => pendingImages.value.push(url))
}

async function onFilePick(e: Event) {
  const el = e.target as HTMLInputElement
  for (const f of Array.from(el.files || [])) {
    try {
      await addPendingFile(f)
    } catch (err) {
      ElMessage.error(`上传失败：${errMsg(err)}`)
    }
  }
  el.value = ''
}

// 粘贴图片/文件：剪贴板有文件项时拦截默认粘贴并加入附件
async function onPaste(e: ClipboardEvent) {
  const items = Array.from(e.clipboardData?.items || [])
  const fileItems = items.filter((it) => it.kind === 'file')
  if (!fileItems.length) return // 纯文本粘贴走默认行为
  e.preventDefault()
  let added = 0
  for (const it of fileItems) {
    const f = it.getAsFile()
    if (!f) continue
    try {
      if (f.type.startsWith('image/')) {
        await addPendingImage(f)
      } else {
        await addPendingFile(f)
      }
      added++
    } catch (err) {
      ElMessage.error(`粘贴附件失败：${errMsg(err)}`)
    }
  }
  if (added) ElMessage.success(`已粘贴 ${added} 个附件`)
}

// Markdown 渲染（AI 回复）与转义（用户文本）
const CURSOR_HTML = '<span class="type-cursor"></span>'
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

// ================= 标本手记 · 动效（纯表现层，不改动上方对话逻辑） =================
const titleEl = ref<HTMLElement>()
const headPin = ref<HTMLElement>()
const sendWrap = ref<HTMLElement>()

// 新消息轻弹入场（只动表现，不动消息数据与滚动逻辑）
watch(
  () => messages.value.length,
  (len, prev) => {
    const added = len - prev
    if (added <= 0) return
    nextTick(() => {
      const rows = bodyEl.value?.querySelectorAll<HTMLElement>('.msg-row')
      if (!rows) return
      const start = Math.max(0, len - added)
      for (let k = start; k < len; k++) popIn(rows[k], (k - start) * 0.12)
    })
  }
)

// 模型设置对话框内容错落入场
watch(settingsVisible, (v) => {
  if (!v) return
  nextTick(() => {
    const box = document.querySelector('.ai-settings')
    if (!box) return
    box.querySelectorAll<HTMLElement>('.anim-item').forEach((el, i) => popIn(el, i * 0.07))
    refreshScroll()
  })
})

onMounted(() => {
  splitReveal(titleEl.value ?? null, 0.15)
  pinPress(headPin.value ?? null, 0.5)
  magnetic(sendWrap.value ?? null)
})
</script>

<style scoped>
/* ============ 手记纸卡 ============ */
.chat-page { padding: 16px 20px; height: calc(100vh - 60px); display: flex; }
.chat-card {
  flex: 1; display: flex; flex-direction: column; padding: 0; overflow: hidden;
  max-width: 1000px; margin: 0 auto; height: 100%;
}
.chat-card:hover { transform: none; box-shadow: var(--shadow-lg); }

/* —— 头部 —— */
.chat-head {
  position: relative;
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px; border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}
.head-left { display: flex; align-items: center; gap: 12px; }
.head-pin { position: static; flex-shrink: 0; }
.head-text { display: flex; flex-direction: column; gap: 3px; }
.title {
  font-family: var(--serif); font-weight: 700; font-size: 18px;
  letter-spacing: 0.05em; color: var(--ink);
}
.model-tag {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--pin);
  border: 1px solid var(--pin); background: var(--pin-soft); border-radius: 2px;
  padding: 4px 10px; transform: rotate(-2deg); white-space: nowrap;
}
.head-actions { display: flex; align-items: center; gap: 4px; margin-right: 64px; }
.head-actions .el-button { color: var(--ink-soft); letter-spacing: 0.1em; }
.head-actions .el-button:hover { color: var(--green); }

/* —— 消息区（横线记录纸） —— */
.chat-body {
  flex: 1; overflow-y: auto; padding: 18px 22px; background: var(--paper);
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0 27px,
    rgba(185, 170, 142, 0.16) 27px 28px
  );
}
.chat-empty { position: relative; text-align: center; color: var(--ink-faint); margin-top: 64px; }
.chat-empty .kicker { margin-bottom: 14px; }
.chat-empty p { margin: 10px 0 4px; font-size: 14px; }
.chat-empty .lead-text {
  font-family: var(--kai); font-size: 15px; color: var(--ink-soft); letter-spacing: 0.06em;
}

/* —— 透明装饰素材（标本点缀，纯表现层） —— */
.deco { position: absolute; pointer-events: none; user-select: none; z-index: 2; }
.deco-butterfly {
  width: 75px; top: -22px; right: -10px;
  transform: rotate(-6deg); opacity: 0.8;
}
.deco-fern {
  width: 110px; left: 6%; top: -44px;
  transform: rotate(-9deg); opacity: 0.8;
}

.msg-row { display: flex; margin-bottom: 16px; gap: 10px; align-items: flex-start; }
.msg-row.user { justify-content: flex-end; }
.avatar { flex-shrink: 0; }
.ai-avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--green); color: var(--paper-2);
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.12em;
  display: flex; align-items: center; justify-content: center;
  box-shadow: var(--shadow-sm);
}
.user-avatar {
  background: var(--sage); color: var(--paper-2);
  font-family: var(--serif); font-size: 13px;
}
.bubble {
  max-width: 72%; padding: 11px 15px; border-radius: var(--radius);
  font-size: 14px; line-height: 1.75; word-break: break-word; position: relative;
  box-shadow: var(--shadow-sm);
}
/* AI = 楷体批注条：左侧虚线引线 */
.bubble.assistant {
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-left: 2px dashed var(--line-strong);
  border-radius: 2px;
}
.bubble.assistant .content { font-family: var(--kai); color: var(--ink-soft); letter-spacing: 0.03em; }
/* 用户 = 采集便签：纸条 + 胶带小角 */
.bubble.user {
  background: var(--paper-3);
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  transform: rotate(-1.1deg);
  padding: 12px 16px;
  color: var(--ink);
}
.bubble.user .content { font-family: var(--kai); letter-spacing: 0.03em; }
.note-tape {
  width: 52px; height: 15px; top: -8px; right: -14px;
  transform: rotate(36deg);
  background: rgba(222, 208, 178, 0.75);
}
.content { white-space: pre-wrap; }

/* —— 打字机光标 —— */
.content.md :deep(.type-cursor) {
  display: inline-block; width: 2px; height: 1em; background: var(--green);
  vertical-align: -0.14em; margin-left: 2px;
  animation: cursor-blink 0.85s step-end infinite;
}
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* —— 粘贴/选择的附件预览 —— */
.pending-row {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;
}
.pending-item {
  position: relative; border: 1px dashed var(--line-strong); border-radius: 2px;
  background: var(--paper-3); padding: 3px; line-height: 0;
}
.pending-thumb { height: 44px; width: auto; display: block; border-radius: 1px; }
.pending-doc {
  display: flex; align-items: center; gap: 5px; padding: 6px 22px 6px 10px;
  color: var(--green); font-family: var(--mono); font-size: 12px; letter-spacing: 0.06em;
}
.pend-name { line-height: 1.2; }
.pend-del {
  position: absolute; top: -7px; right: -7px; width: 16px; height: 16px;
  border-radius: 50%; background: var(--ink-soft); color: var(--paper-2);
  font-size: 11px; line-height: 15px; text-align: center; cursor: pointer;
  opacity: 0; transition: opacity 0.15s;
}
.pending-item:hover .pend-del { opacity: 1; }
.pend-del:hover { background: var(--pin); }

/* —— 标本铭牌（发送的商品卡片） —— */
.prod-card {
  display: flex; align-items: center; gap: 12px; padding: 11px;
  background: var(--paper-2); border: 1px solid var(--line-strong); border-radius: 2px;
  margin-bottom: 10px; min-width: 250px; max-width: 340px; position: relative;
}
.prod-card::before {
  content: ""; position: absolute; inset: 3px;
  border: 1px dashed rgba(185, 170, 142, 0.55); border-radius: 1px; pointer-events: none;
}
.pc-frame {
  padding: 4px; background: var(--paper-3); border: 1px solid var(--line);
  flex-shrink: 0; line-height: 0;
}
.pc-img { width: 52px; height: 52px; object-fit: contain; background: var(--paper-2); display: block; }
.pc-info { flex: 1; min-width: 0; }
.pc-no {
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.18em;
  color: var(--ink-faint); margin-bottom: 2px;
}
.pc-name {
  font-family: var(--serif); font-size: 13px; color: var(--ink); line-height: 1.45; font-weight: 700;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.pc-price { font-size: 14px; margin-top: 3px; }
.pc-price.price { letter-spacing: 0.02em; }
.pc-arrow { flex-shrink: 0; color: var(--ink-faint); opacity: 0.8; }

/* —— AI 回复 Markdown 排版 —— */
.content.md { white-space: normal; }
.md :deep(h1), .md :deep(h2), .md :deep(h3), .md :deep(h4) {
  margin: 12px 0 6px; font-weight: 700; color: var(--ink); line-height: 1.4;
  font-family: var(--serif); letter-spacing: 0.03em;
}
.md :deep(h1) { font-size: 17px; }
.md :deep(h2) { font-size: 16px; border-bottom: 1px solid var(--line); padding-bottom: 4px; }
.md :deep(h3) { font-size: 15px; }
.md :deep(h4) { font-size: 14px; }
.md :deep(p) { margin: 6px 0; line-height: 1.8; }
.md :deep(ul), .md :deep(ol) { margin: 6px 0; padding-left: 20px; }
.md :deep(li) { margin: 3px 0; line-height: 1.75; }
.md :deep(strong) { color: var(--ink); }
.md :deep(a) { color: var(--green); text-decoration: underline dotted; }
.md :deep(code) {
  background: var(--paper-3); padding: 1px 5px; border-radius: 2px;
  font-size: 13px; font-family: var(--mono); color: var(--pin);
}
.md :deep(pre) {
  background: var(--paper-3); padding: 10px; border-radius: 2px; overflow-x: auto;
  border: 1px solid var(--line);
}
.md :deep(pre code) { background: none; padding: 0; color: var(--ink-soft); }
.md :deep(hr) { border: none; border-top: 1px dashed var(--line-strong); margin: 10px 0; }
.md :deep(blockquote) {
  border-left: 3px solid var(--pin); margin: 8px 0; padding: 4px 12px;
  color: var(--ink-soft); background: var(--pin-soft); font-family: var(--kai);
}
.md :deep(table) {
  border-collapse: collapse; margin: 8px 0; font-size: 13px; width: 100%;
}
.md :deep(th), .md :deep(td) {
  border: 1px solid var(--line); padding: 6px 10px; text-align: left;
}
.md :deep(th) { background: var(--paper-3); font-weight: 600; }
.md :deep(img) { max-width: 100%; border-radius: 2px; border: 1px solid var(--line); }

.imgs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.msg-img {
  max-width: 200px; max-height: 160px; border-radius: 2px;
  border: 1px solid var(--line); padding: 3px; background: var(--paper-2);
}
.files { margin-bottom: 6px; }
.file-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px;
  background: var(--paper-3); border: 1px dashed var(--line-strong); border-radius: 2px;
  font-family: var(--mono); font-size: 12px; letter-spacing: 0.06em; color: var(--green);
  text-decoration: none; margin: 2px 4px 2px 0;
}
.file-chip:hover { background: var(--green-soft); border-color: var(--green); }

/* —— 打字指示：记录中… —— */
.typing { display: flex; align-items: center; gap: 5px; height: 24px; }
.rec-label {
  font-family: var(--kai); color: var(--ink-faint); font-size: 12px; letter-spacing: 0.14em;
}
.pen-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--pin);
  animation: blink 1.2s infinite both;
}
.pen-dot:nth-child(3) { animation-delay: .2s; }
.pen-dot:nth-child(4) { animation-delay: .4s; }
.typing em {
  font-style: normal; color: var(--ink-faint); font-size: 12px; margin-left: 6px; font-family: var(--kai);
}
@keyframes blink {
  0%, 80%, 100% { opacity: .25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

/* —— 输入区：观察记录纸 —— */
.input-bar {
  padding: 10px 18px 14px; background: var(--paper-2); border-top: 1px solid var(--line);
}
.input-head { margin-bottom: 8px; }
.input-main { display: flex; gap: 12px; align-items: flex-end; }
.input-main .el-input { flex: 1; }
.input-main :deep(.el-textarea__inner) {
  background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius);
  box-shadow: none; font-family: var(--kai); font-size: 14px; line-height: 1.7;
  letter-spacing: 0.03em; padding: 10px 12px;
}
.input-main :deep(.el-textarea__inner:focus) {
  border-color: var(--green); box-shadow: 0 0 0 1.5px rgba(60, 90, 69, 0.18);
}
.btn-col { display: flex; gap: 8px; align-items: center; }
.send-wrap { display: inline-flex; }
.send-btn {
  width: 92px; font-family: var(--serif); letter-spacing: 0.28em; text-indent: 0.28em;
}
.plus-btn { flex-shrink: 0; }

/* —— 拓展面板：标本工具箱 —— */
.plus-panel { max-height: 380px; overflow-y: auto; }
.panel-title {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--ink-faint); margin-bottom: 10px; text-transform: uppercase;
}
.panel-grid { display: flex; gap: 14px; }
.panel-item {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  cursor: pointer; font-size: 12px; color: var(--ink-soft); letter-spacing: 0.08em;
}
.panel-item:hover { color: var(--green); }
.panel-icon {
  width: 54px; height: 54px; border-radius: 2px; display: flex;
  align-items: center; justify-content: center;
  background: var(--paper-3); color: var(--ink-soft);
  border: 1px dashed var(--line-strong);
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.panel-item:hover .panel-icon {
  background: var(--green-soft); color: var(--green); border-color: var(--green);
  transform: translateY(-3px);
}
.img-icon { background: var(--paper-3); color: var(--green); }
.file-icon { background: var(--paper-3); color: var(--sage); }
.fav-icon { background: var(--pin-soft); color: var(--pin); }

.fav-list { max-height: 220px; overflow-y: auto; }
.fav-item {
  display: flex; align-items: center; gap: 10px; padding: 8px;
  border-radius: 2px; cursor: pointer;
  border-bottom: 1px dashed var(--line);
  transition: background 0.15s;
}
.fav-item:last-child { border-bottom: none; }
.fav-item:hover { background: var(--green-soft); }
.fav-img {
  width: 40px; height: 40px; object-fit: contain; background: var(--paper-2);
  border: 1px solid var(--line); border-radius: 1px; flex-shrink: 0;
}
.fav-info { flex: 1; min-width: 0; }
.fav-name {
  font-family: var(--kai); font-size: 13px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; color: var(--ink);
}
.fav-price { font-size: 12px; display: flex; gap: 8px; margin-top: 2px; }

/* —— 模型设置：MODEL REGISTRY —— */
.ai-settings .anim-item { position: relative; }
.ai-settings :deep(.el-form-item__label) { justify-content: flex-start; }
.fld {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--ink-faint); text-transform: uppercase; white-space: nowrap;
}
.cfg-specimen {
  border: 1px dashed var(--line-strong); background: var(--paper-3);
  border-radius: 2px; padding: 12px 14px;
  box-shadow: inset 0 0 0 3px var(--paper-3), inset 0 0 0 4px rgba(185, 170, 142, 0.3);
}
</style>
