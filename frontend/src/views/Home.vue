/**
 * 首页（标本展位）：全网商品实时比价检索与浏览入口。
 * 支持关键词搜索、粘贴商品链接直达详情、上传图片识图找同款，
 * 并提供分类筛选、排序与客户端分页，点击商品卡片进入实时详情页。
 */
<template>
  <div class="page" ref="pageRef">
    <!-- 页头 -->
    <div class="page-head">
      <div class="kicker"><span class="pin-dot"></span>PLATE Ⅰ · SPECIMEN CABINET</div>
      <h1 class="page-title" ref="titleRef">标本展位</h1>
      <p class="page-sub">陈列全网商品标本，注记每一次价格呼吸。</p>
      <img class="deco deco-magnifier-head" src="/deco/magnifier.png" alt="" aria-hidden="true" />
    </div>

    <!-- 采集台 -->
    <div class="spec-card desk reveal">
      <img class="deco deco-tape-desk" src="/deco/washi-tape.png" alt="" aria-hidden="true" />
      <span class="tape t-bl"></span>
      <span class="tape t-br"></span>
      <div class="kicker desk-kicker"><span class="pin-dot"></span>SPECIMEN COLLECTION · 采集台</div>
      <div class="search-row">
        <el-input
          v-model="keyword"
          size="large"
          placeholder="输入商品关键词实时比价搜索，或粘贴商品链接直接查看详情，如：iPhone / https://item.jd.com/xxx.html"
          clearable
          @keyup.enter="onSubmit"
        >
          <template #append>
            <span class="magnetic btn-magnet" ref="searchBtnRef">
              <el-button size="large" type="primary" @click="onSubmit">
                <el-icon v-if="!isUrlInput" style="margin-right: 4px"><Search /></el-icon>
                {{ isUrlInput ? '查看商品' : '搜索' }}
              </el-button>
            </span>
          </template>
        </el-input>
        <el-button size="large" class="mag-btn vis-btn" @click="pickVisionImage">
          <el-icon style="margin-right: 4px"><Camera /></el-icon>识图找同款
        </el-button>
      </div>
      <!-- 索引卡：分类 / 排序 -->
      <div class="filters">
        <div class="idx-block">
          <div class="kicker"><span class="pin-dot"></span>INDEX · 分类索引（同慢慢买）</div>
          <el-radio-group v-model="category" size="small" @change="search(1)">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button v-for="c in categories" :key="c.code" :label="c.code">
              {{ c.name }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="idx-block idx-sort">
          <div class="kicker">SORT · 排序方式</div>
          <el-radio-group v-model="sort" size="small" @change="page = 1">
            <el-radio-button label="random">随机</el-radio-button>
            <el-radio-button label="price_asc">价格从低到高</el-radio-button>
            <el-radio-button label="price_desc">价格从高到低</el-radio-button>
            <el-radio-button label="newest">最新上架</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>

    <!-- 标本展位 -->
    <div class="shelf-head">
      <div class="kicker"><span class="pin-dot"></span>SPECIMEN SHELF · 标本展位</div>
      <div class="annot shelf-count">
        <span v-if="loading && !allItems.length" class="sk-status">
          <span class="rec-label">标本采集中</span>
          <span class="pen-dot"></span><span class="pen-dot"></span><span class="pen-dot"></span>
        </span>
        <template v-else>在架标本 {{ total }} 件 · 实时来自慢慢买</template>
      </div>
    </div>

    <!-- 加载占位：骨架标本卡（遮盖实时爬取的空白期） -->
    <div v-if="loading && !allItems.length" class="grid skeleton">
      <div v-for="i in 18" :key="i" class="sk-card spec-card">
        <div class="sk-line sk-lot"></div>
        <div class="sk-img"></div>
        <div class="sk-line"></div>
        <div class="sk-line sk-short"></div>
        <div class="sk-line sk-note"></div>
      </div>
    </div>

    <!-- 商品卡片网格：循环渲染当前页标本，点击卡片进入实时详情 -->
    <div v-else v-loading="loading" element-loading-text="标本采集中" class="grid" ref="gridRef">
      <div
        v-for="(p, i) in displayItems"
        :key="p.url"
        class="item spec-card reveal"
        :data-delay="(i % 9) * 70"
        @click="openProduct(p)"
      >
        <span class="pin lot-pin"></span>
        <div class="lot-no">LOT {{ lotNo(i) }}</div>
        <div class="img-wrap">
          <img :src="p.image || placeholder" alt="" />
        </div>
        <div class="name" :title="p.title">{{ p.title }}</div>
        <div class="meta">
          <span class="price" v-if="p.price" :data-count="p.price" data-prefix="￥">￥{{ p.price }}</span>
          <span class="muted" v-else>暂无价格</span>
        </div>
        <div class="annot note lead-line">{{ specimenNote(p) }}</div>
      </div>
      <el-empty v-if="!loading && !displayItems.length" description="没有找到相关商品" />
    </div>

    <div class="pager" v-if="total > 0">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="(p: number) => search(p)"
      />
      <img class="deco deco-maple-shelf" src="/deco/maple-leaf.png" alt="" aria-hidden="true" />
    </div>

    <div class="colophon page-foot">PRICE TRACE · 标本手记 —— 每一件商品，都是一枚被记录的价格标本。</div>

    <!-- 识图找同款（多模态闭环：图片 -> 视觉识别 -> 候选商品 -> 查看详情） -->
    <input ref="visInput" type="file" accept="image/*" multiple style="display: none" @change="onVisPick" />
    <el-dialog v-model="visionVisible" title="识图找同款" width="480px">
      <div v-if="visionLoading" class="vision-loading">
        <span class="rec-label">正在识别图片中的商品</span>
        <span class="pen-dot"></span><span class="pen-dot"></span><span class="pen-dot"></span>
      </div>
      <template v-else-if="visionResult">
        <div class="kicker"><span class="pin-dot"></span>识别结果<span v-if="visionResult.keywords">：{{ visionResult.keywords }}</span></div>
        <p v-if="visionResult.message" class="muted">{{ visionResult.message }}</p>
        <!-- 候选商品列表：点击任一项跳转对应详情页（本地库 / 联网实时） -->
        <div class="vision-list">
          <div
            v-for="(c, i) in visionResult.candidates"
            :key="i"
            class="vision-item"
            @click="pickCandidate(c)"
          >
            <img :src="c.image || placeholder" class="vision-img" />
            <div class="vision-info">
              <div class="vision-name">{{ c.name }}</div>
              <div class="vision-meta">
                <span v-if="c.price" class="price">￥{{ c.price }}</span>
                <span class="src-tag">{{ c.source }}<template v-if="c.platform"> · {{ c.platform }}</template></span>
              </div>
            </div>
            <el-button size="small" type="primary" plain round>查看</el-button>
          </div>
          <el-empty
            v-if="!visionResult.candidates?.length"
            description="没有找到候选商品，换个图试试"
            :image-size="60"
          />
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import api, { errMsg } from '../api'
import { splitReveal, revealOnScroll, refreshScroll, countUp, magnetic, tiltCard, pinPress } from '../anim'

const router = useRouter()
// 商品缺图时的兜底占位图
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20icon%20shopping%20bag%20flat%20design&image_size=square'

// 搜索输入框内容：支持商品关键词或商品链接（链接直达详情）
const keyword = ref('')
// 当前分类编码，空串表示"全部"
const category = ref('')
// 排序方式：random / price_asc / price_desc / newest
const sort = ref('random')
// 当前页码（客户端分页，数据一次性取回）
const page = ref(1)
const pageSize = 18 // 每页 2 行 × 9 列
// 慢慢买实时检索到的全量商品，排序与分页均在客户端完成
const allItems = ref<any[]>([])
// 分类索引列表（供分类筛选单选组使用）
const categories = ref<any[]>([])
// 检索加载态：首次加载时用骨架卡遮盖实时爬取的空白期
const loading = ref(false)

// —— 标本手记动效 ——
const pageRef = ref<HTMLElement | null>(null)
const gridRef = ref<HTMLElement | null>(null)
const titleRef = ref<HTMLElement | null>(null)
const searchBtnRef = ref<HTMLElement | null>(null)

// 排序 + 客户端分页（实时数据一次性取回）
const displayItems = computed(() => {
  const arr = [...allItems.value]
  if (sort.value === 'random') arr.sort(() => Math.random() - 0.5)
  else if (sort.value === 'price_asc') arr.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity))
  else if (sort.value === 'price_desc') arr.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity))
  // newest：保持慢慢买返回顺序（默认即最新）
  return arr.slice((page.value - 1) * pageSize, page.value * pageSize)
})
const total = computed(() => allItems.value.length)

function lotNo(i: number) {
  return String((page.value - 1) * pageSize + i + 1).padStart(3, '0')
}
// 拼接标本注记：标签 / 平台 / 时间，缺项则用默认观测语
function specimenNote(p: any) {
  const bits = [p.tag, p.platform, p.time].filter(Boolean)
  return bits.length ? bits.join(' · ') : '全网采集 · 持续观测'
}

// 清理/重建 root 内的 ScrollTrigger（换页 / 异步刷新时）
function rescanReveals(root: HTMLElement | null) {
  if (!root) return
  ScrollTrigger.getAll().forEach((t) => {
    if (t.trigger && root.contains(t.trigger)) t.kill()
  })
  revealOnScroll(root)
}

// 搜索结果到位后：图钉按入 + 价格滚动 + 卡片倾斜 + 入场重扫
watch(displayItems, async () => {
  await nextTick()
  const grid = gridRef.value
  if (!grid) return
  grid.querySelectorAll<HTMLElement>('.lot-pin').forEach((el, i) => pinPress(el, 0.1 + i * 0.07))
  grid.querySelectorAll<HTMLElement>('.price[data-count]').forEach((el) => {
    // 整数价格用滚动数字呈现，小数价保留精确值
    if (Number.isInteger(parseFloat(el.dataset.count || ''))) countUp(el)
  })
  grid.querySelectorAll<HTMLElement>('.item').forEach((el) => {
    if (el.dataset.tilt !== '1') {
      el.dataset.tilt = '1'
      tiltCard(el)
    }
  })
  rescanReveals(grid)
  refreshScroll()
})

// 搜索栏输入是否为商品链接（直接进详情）
const isUrlInput = computed(() => /^https?:\/\/\S+$/i.test(keyword.value.trim()))

// 统一提交入口：链接 -> 实时详情；关键词 -> 慢慢买实时搜索
function onSubmit() {
  const kw = keyword.value.trim()
  if (!kw) return search(1)
  if (isUrlInput.value) {
    return router.push({ path: '/product/live', query: { url: kw, deal: '0' } })
  }
  return search(1)
}

// 实时从慢慢买获取商品列表（关键词走比价搜索，分类/默认走全网折扣分类页）
async function search(p = 1) {
  page.value = p
  loading.value = true
  try {
    const { data } = await api.get('/api/products/live-search', {
      params: { keyword: keyword.value.trim(), category: category.value, n: 36 },
      timeout: 90000, // 实时爬取慢慢买，给足超时
    })
    allItems.value = data.items
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  const { data } = await api.get('/api/products/categories')
  categories.value = data
}

// —— 识图找同款（与 AI 导购页同款能力：视觉识别 -> 候选 -> 查看详情） ——
// 识图返回的候选商品：product_id 非空为本地库商品，否则为联网实时结果
interface VisionCandidate {
  product_id: number | null
  name: string
  price: number | null
  image: string
  platform: string
  url?: string
  source: string
}
// 隐藏的文件选择框：识图上传图片的入口
const visInput = ref<HTMLInputElement>()
// 识图结果弹窗的可见性
const visionVisible = ref(false)
// 识图请求进行中（弹窗内展示识别动效）
const visionLoading = ref(false)
// 识图结果：识别关键词 + 候选商品列表
const visionResult = ref<{ keywords: string; message?: string; candidates: VisionCandidate[] } | null>(null)

function pickVisionImage() {
  visInput.value?.click()
}

// 将图片文件读为 base64 DataURL，便于随请求体传给识图接口
function readDataURL(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(f)
  })
}

/**
 * 处理识图图片选择：读取图片为 DataURL 并调用识图接口，
 * 成功后在弹窗中展示识别关键词与候选商品，失败则提示并关闭弹窗。
 */
async function onVisPick(e: Event) {
  const el = e.target as HTMLInputElement
  const files = Array.from(el.files || []).slice(0, 2)
  el.value = ''
  if (!files.length) return
  const images = await Promise.all(files.map(readDataURL))
  visionVisible.value = true
  visionLoading.value = true
  visionResult.value = null
  try {
    const { data } = await api.post('/api/advisor/image_search', { images }, { timeout: 90000 })
    if (data.ok === false) {
      visionVisible.value = false
      ElMessage.error(data.error || '识图失败')
      return
    }
    visionResult.value = { keywords: data.keywords || '', message: data.message, candidates: data.candidates || [] }
  } catch (err) {
    visionVisible.value = false
    ElMessage.error('识图失败：' + errMsg(err))
  } finally {
    visionLoading.value = false
  }
}

// 候选 -> 本地库商品进详情；联网候选走实时详情
function pickCandidate(c: VisionCandidate) {
  visionVisible.value = false
  if (c.product_id) {
    router.push(`/product/${c.product_id}`)
    return
  }
  router.push({
    path: '/product/live',
    query: {
      url: c.url || '',
      title: c.name || '',
      price: c.price != null ? String(c.price) : '',
      image: c.image || '',
      platform: c.platform || '',
      deal: '0',
    },
  })
}

// 点击商品 -> 实时详情页（慢慢买数据即查即看，追踪/比价时才入库）
function openProduct(p: any) {
  router.push({
    path: '/product/live',
    query: {
      url: p.url,
      title: p.title || '',
      price: p.price != null ? String(p.price) : '',
      image: p.image || '',
      platform: p.platform || '',
      deal: p.kind === 'deal' ? '1' : '0',
    },
  })
}

onMounted(() => {
  splitReveal(titleRef.value, 0.05)
  magnetic(searchBtnRef.value)
  if (pageRef.value) revealOnScroll(pageRef.value)
  search(1)
  loadCategories()
})

// 页面卸载时清理本页的 ScrollTrigger，避免动效监听泄漏到其他页面
onUnmounted(() => {
  const root = pageRef.value
  if (!root) return
  ScrollTrigger.getAll().forEach((t) => {
    if (t.trigger && root.contains(t.trigger)) t.kill()
  })
})
</script>

<style scoped>
/* —— 页头 —— */
.page-head { position: relative; margin-bottom: 18px; }
.page-sub { margin: 6px 0 0; }

/* —— 采集台 —— */
.desk { padding: 64px 24px 18px; margin-bottom: 18px; }
.desk-kicker { margin-bottom: 12px; }
.tape { position: absolute; }
.t-bl { bottom: -8px; left: 40px; transform: rotate(2deg); }
.t-br { bottom: -8px; right: 40px; transform: rotate(-3deg); }
.btn-magnet { display: inline-flex; }
.btn-magnet :deep(.el-button) { margin-left: 0; }
.search-row { display: flex; align-items: stretch; gap: 10px; }
.search-row :deep(.el-input) { flex: 1; }
.vis-btn { flex-shrink: 0; letter-spacing: 0.1em; }

/* —— 识图找同款 —— */
.vision-loading { display: flex; align-items: center; gap: 5px; height: 40px; }
.vision-list { max-height: 320px; overflow-y: auto; margin-top: 8px; }
.vision-item {
  display: flex; align-items: center; gap: 10px; padding: 8px;
  border-radius: 2px; cursor: pointer; border-bottom: 1px dashed var(--line);
  transition: background 0.15s;
}
.vision-item:last-child { border-bottom: none; }
.vision-item:hover { background: var(--green-soft); }
.vision-img {
  width: 42px; height: 42px; object-fit: contain; background: var(--paper-2);
  border: 1px solid var(--line); border-radius: 1px; flex-shrink: 0;
}
.vision-info { flex: 1; min-width: 0; }
.vision-name {
  font-family: var(--kai); font-size: 13px; color: var(--ink); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.vision-meta { display: flex; gap: 8px; align-items: center; margin-top: 2px; font-size: 12px; }
.src-tag {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; color: var(--ink-faint);
}

/* —— 索引卡：分类 / 排序 —— */
.filters {
  display: flex;
  align-items: flex-start;
  margin-top: 14px;
  gap: 0;
  flex-wrap: wrap;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: rgba(239, 233, 218, 0.5);
  padding: 10px 14px;
}
.idx-block { display: flex; flex-direction: column; gap: 8px; padding: 2px 16px 2px 0; }
.idx-sort {
  border-left: 1px dashed var(--line-strong);
  padding-left: 18px;
  margin-left: 4px;
}
.idx-block .el-radio-group { flex-wrap: wrap; }

/* —— 标本展位 —— */
.shelf-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin: 4px 2px 12px;
  border-bottom: 1px dashed var(--line-strong);
  padding-bottom: 8px;
}
.shelf-count { font-size: 12px; }

/* —— 加载占位：骨架标本卡（遮盖实时爬取的空白期） —— */
.sk-status { display: inline-flex; align-items: center; gap: 5px; }
.rec-label {
  font-family: var(--kai); color: var(--ink-faint); font-size: 12px; letter-spacing: 0.14em;
}
.pen-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--pin);
  animation: pen-blink 1.2s infinite both;
}
.pen-dot:nth-child(3) { animation-delay: .2s; }
.pen-dot:nth-child(4) { animation-delay: .4s; }
@keyframes pen-blink {
  0%, 80%, 100% { opacity: .25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.sk-card { padding: 12px 14px; pointer-events: none; }
.sk-img {
  aspect-ratio: 1 / 1; border: 1px solid var(--line); border-radius: 2px;
  background: var(--paper-3); animation: sk-pulse 1.1s ease-in-out infinite;
}
.sk-line {
  height: 12px; border-radius: 2px; background: var(--paper-3);
  margin-top: 10px; animation: sk-pulse 1.1s ease-in-out infinite;
}
.sk-lot { width: 40%; height: 9px; margin-top: 0; }
.sk-short { width: 55%; }
.sk-note { width: 75%; height: 9px; margin-top: 12px; }
.sk-card:nth-child(2n) :is(.sk-img, .sk-line) { animation-delay: .3s; }
.sk-card:nth-child(3n) :is(.sk-img, .sk-line) { animation-delay: .6s; }
@keyframes sk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .45; }
}
.grid {
  display: grid; grid-template-columns: repeat(9, 1fr);
  gap: 16px; min-height: 200px;
}
.item {
  cursor: pointer;
  padding: 12px 14px 12px;
  transition: box-shadow .25s; /* transform 由 GSAP tiltCard 驱动，避免叠加拖影 */
}
.item:hover { box-shadow: var(--shadow-lg); }
.item::after {
  content: "";
  position: absolute; inset: 0;
  border-radius: var(--radius);
  background: radial-gradient(220px circle at var(--gx, 50%) var(--gy, 0%), rgba(60, 90, 69, 0.09), transparent 70%);
  opacity: 0;
  transition: opacity .35s;
  pointer-events: none;
}
.item:hover::after { opacity: 1; }
.lot-pin { top: -5px; right: 16px; }
.lot-no {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--ink-faint); margin-bottom: 8px;
}
.img-wrap {
  aspect-ratio: 1 / 1; /* 随卡宽等比缩放（缩放自适应） */
  display: flex; align-items: center; justify-content: center;
  background: var(--paper-3);
  border: 1px solid var(--line);
  border-radius: 2px;
  box-shadow: inset 0 0 0 3px var(--paper-2);
  overflow: hidden;
  padding: 8px;
}
.img-wrap img {
  max-width: 100%; max-height: 100%; object-fit: contain;
  transition: transform .45s cubic-bezier(.2, .7, .3, 1);
}
/* 悬停图片放大（3D 悬浮配套效果，img-wrap overflow 裁切） */
.item:hover .img-wrap img { transform: scale(1.12); }
.name {
  margin: 10px 0 6px;
  font-family: var(--serif); font-size: 14px; line-height: 1.45;
  height: 41px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.meta { display: flex; align-items: center; justify-content: space-between; }
.meta .price { font-size: 16px; }
.note {
  font-size: 11px; margin-top: 8px; padding-top: 6px;
  color: var(--ink-faint);
  transition: color .25s;
}
.item:hover .note { color: var(--ink-soft); }

/* —— 分页 / 页脚 —— */
.pager { position: relative; display: flex; justify-content: center; margin-top: 18px; }
.page-foot { margin-top: 26px; text-align: center; }

/* —— 透明装饰素材 —— */
.deco { position: absolute; pointer-events: none; z-index: 3; }
.deco-tape-desk { width: 150px; top: -32px; left: 22px; transform: rotate(-4deg); }
.deco-magnifier-head { width: 95px; top: -6px; right: 2px; opacity: 0.8; transform: rotate(-8deg); }
.deco-maple-shelf { width: 95px; top: -12px; right: 4px; opacity: 0.8; transform: rotate(10deg); }

/* 缩放自适应：窗口/缩放小于全屏宽度后按卡宽自动降列，保证卡片不被挤压 */
@media (max-width: 1800px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
}
@media (max-width: 1440px) {
  .idx-sort { margin-left: 0; }
}
@media (max-width: 900px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
}
</style>
