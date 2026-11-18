/**
 * AI 导购聊天的会话/消息状态管理：提供多会话的创建、切换、删除，消息读写，
 * 以及会话数据的 localStorage 持久化。
 */
import { computed, ref, watch } from 'vue'

// ================= 多会话共享存储（模块级单例） =================
// 会话状态放在模块级：路由切走导致组件销毁时，流式回复仍继续写入并落盘，
// 切回页面实时续显，不再出现"切走即断"。

// 购买建议卡数据：AI 结构化输出的购买动作、置信度、摘要与支撑依据
export interface AdviceCardData {
  action: 'buy' | 'wait' | 'watch'
  confidence: number
  summary: string
  evidence: string[]
}

// 单条消息：正文之外可携带商品上下文、Agent 工具调用过程、建议卡与 RAG 引用来源等扩展信息
export interface Msg {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  typing?: boolean // 打字机逐字输出中
  tip?: string
  fallback?: boolean
  images?: string[]
  files?: { name: string; url: string }[]
  productInfo?: { id: number; name: string; price: number | null; image: string }
  raw?: string // 发送给 AI 的原文（含 [[product:N]] 标记）
  toolEvents?: { name: string; status: string; summary?: string }[] // Agent 工具调用过程
  adviceCard?: AdviceCardData // 购买建议卡（结构化输出）
  sources?: { id: number; title: string }[] // 知识库引用来源（RAG 溯源）
}

// 会话：一次对话的元信息（标题、时间）与完整消息列表
export interface Session {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: Msg[]
}

const SESSIONS_KEY = 'spt_advisor_sessions'
const LEGACY_CHAT_KEY = 'spt_advisor_chat' // 旧版单会话存档（迁移用）
export const MAX_SESSIONS = 20

// 新会话开场白：引导用户发商品链接、收藏商品或直接提问
const WELCOME_TEXT =
  '你好，我是 AI 智能导购。\n' +
  '· 发送商品链接，我会抓取它的历史价格帮你分析\n' +
  '· 点击右侧 + → 收藏商品，把价格追踪的商品发给我\n' +
  '· 也可以直接问我什么时候买最划算'

function newSessionId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

function makeSession(msgs: Msg[] = []): Session {
  return { id: newSessionId(), title: '新对话', createdAt: Date.now(), updatedAt: Date.now(), messages: msgs }
}

// 恢复时重置未完成的加载/打字态（整页刷新中断的流）
function resetInterrupted(msgs: Msg[]) {
  for (const m of msgs) {
    if (m.loading || m.typing) {
      m.loading = false
      m.typing = false
      m.content = m.content || '（上次对话被中断，请重新发送）'
    }
  }
}

/** 从 localStorage 恢复会话列表；无存档时尝试把旧版单会话数据迁移为首个历史会话 */
function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (raw) {
      const list: Session[] = JSON.parse(raw)
      for (const s of list) resetInterrupted(s.messages)
      return list
    }
  } catch {
    /* 解析失败则尝试旧版存档 */
  }
  // 旧版单会话（sessionStorage）迁移为首个历史会话
  try {
    const saved = sessionStorage.getItem(LEGACY_CHAT_KEY)
    if (saved) {
      const msgs: Msg[] = JSON.parse(saved)
      resetInterrupted(msgs)
      return [makeSession(msgs)]
    }
  } catch {
    /* 无旧存档 */
  }
  return []
}

// 全部会话列表；为空时初始化一个含欢迎语的默认会话
export const sessions = ref<Session[]>(loadSessions())
if (!sessions.value.length) {
  sessions.value = [makeSession([{ role: 'assistant', content: WELCOME_TEXT }])]
}
// 当前会话 ID，默认指向最近使用（列表末尾）的会话
export const currentId = ref(sessions.value[sessions.value.length - 1]?.id || '')
// 当前会话对象（按 currentId 查找，找不到时兜底为第一个会话）
export const currentSession = computed(
  () => sessions.value.find((s) => s.id === currentId.value) || sessions.value[0]
)
// 当前会话的消息列表（可读写计算属性，写入时回写当前会话）
export const messages = computed<Msg[]>({
  get: () => currentSession.value?.messages ?? [],
  set: (v) => {
    if (currentSession.value) currentSession.value.messages = v
  },
})

// 按最近活跃时间倒序的会话列表（侧边栏展示与超量淘汰排序使用）
export const sortedSessions = computed(() =>
  [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt)
)

// 会话内最近聊过的商品：后续追问（如"输出购买建议卡片"）自动携带商品上下文
export const sessionProductId = computed(() => {
  const list = messages.value
  for (let i = list.length - 1; i >= 0; i--) {
    const id = list[i].productInfo?.id
    if (id) return id
  }
  return null
})

// 是否正在发送/等待 AI 回复（用于禁用输入框、防止并发发送）
export const sending = ref(false)

// 持续落盘：模块级 watcher 不随组件销毁停止
watch(
  sessions,
  (v) => {
    try {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify(v))
    } catch {
      /* 存储超限忽略 */
    }
  },
  { deep: true }
)

/** 新建会话并置为当前；会话数超过上限时淘汰最久未活跃的非当前会话 */
export function newChat() {
  if (!currentSession.value?.messages.length) return // 当前已是空会话
  const s = makeSession([])
  sessions.value.unshift(s)
  currentId.value = s.id
  if (sessions.value.length > MAX_SESSIONS) {
    // 保留最近 MAX_SESSIONS 个会话（优先淘汰最久未活跃的非当前会话）
    const rest = sortedSessions.value.filter((x) => x.id !== s.id)
    const drop = rest.slice(MAX_SESSIONS - 1)
    for (const d of drop) removeSession(d.id)
  }
}

export function switchSession(id: string) {
  currentId.value = id
}

/** 删除指定会话；删的是当前会话时自动切到剩余的第一个，且始终保留至少一个会话 */
export function removeSession(id: string) {
  const idx = sessions.value.findIndex((s) => s.id === id)
  if (idx < 0) return
  sessions.value.splice(idx, 1)
  if (!sessions.value.length) sessions.value = [makeSession([])]
  if (currentId.value === id) currentId.value = sessions.value[0].id
}
