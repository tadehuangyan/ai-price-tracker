<template>
  <div class="page" ref="pageRef">
    <!-- 页头 -->
    <div class="page-head">
      <div class="kicker"><span class="pin-dot"></span>PLATE Ⅰ · SPECIMEN CABINET</div>
      <h1 class="page-title" ref="titleRef">标本展位</h1>
      <p class="page-sub">陈列全网商品标本，注记每一次价格呼吸。</p>
      <img class="deco deco-fern-head" src="/deco/fern-sprig.png" alt="" aria-hidden="true" />
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
          placeholder="输入商品关键词搜索，或粘贴商品链接即时采集，如：iPhone / https://item.jd.com/xxx.html"
          clearable
          @keyup.enter="onSubmit"
        >
          <template #append>
            <span class="magnetic btn-magnet" ref="searchBtnRef">
              <el-button size="large" type="primary" :loading="realtimeLoading" @click="onSubmit">
                <el-icon v-if="!isUrlInput" style="margin-right: 4px"><Search /></el-icon>
                {{ isUrlInput ? '即时采集' : '搜索' }}
              </el-button>
            </span>
          </template>
        </el-input>
      </div>
      <div v-if="realtimeResult" class="realtime-result">
        <el-alert type="success" :closable="false" show-icon @close="realtimeResult = null">
          <template #title>
            采集成功：{{ realtimeResult.title || '（无标题）' }} ——
            <b class="price">￥{{ realtimeResult.price }}</b>
            （{{ realtimeResult.platform }} · {{ realtimeResult.captured_at }}）
          </template>
        </el-alert>
      </div>
      <!-- 索引卡：分类 / 排序 -->
      <div class="filters">
        <div class="idx-block">
          <div class="kicker"><span class="pin-dot"></span>INDEX · 分类索引</div>
          <el-radio-group v-model="category" size="small" @change="search(1)">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button v-for="c in categories" :key="c.category" :label="c.category">
              {{ c.category }}（{{ c.count }}）
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="idx-block idx-sort">
          <div class="kicker">SORT · 排序方式</div>
          <el-radio-group v-model="sort" size="small" @change="search(1)">
            <el-radio-button label="random">随机</el-radio-button>
            <el-radio-button label="price_asc">价格从低到高</el-radio-button>
            <el-radio-button label="price_desc">价格从高到低</el-radio-button>
            <el-radio-button label="newest">最新上架</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>

    <!-- 野外新采集：数据库之外的实时商品 -->
    <div class="spec-card discover-card reveal" data-delay="80" v-if="discoverItems.length || discoverLoading">
      <span class="pin d-pin"></span>
      <div class="discover-head">
        <div>
          <div class="kicker"><span class="pin-dot"></span>FIELD COLLECTION · 野外记录</div>
          <div class="head-row">
            <span class="block-title">野外新采集</span>
            <span class="seal seal-sm">新到</span>
          </div>
        </div>
        <el-button size="small" class="magnetic-lite" :loading="discoverLoading" @click="loadDiscover(1)">
          <el-icon style="margin-right: 4px"><Refresh /></el-icon>换一批
        </el-button>
      </div>
      <div v-loading="discoverLoading" class="discover-grid">
        <div
          v-for="d in discoverItems"
          :key="d.url"
          class="discover-item"
          @click="importProduct(d)"
        >
          <div class="d-img">
            <img :src="d.image || placeholder" alt="" />
          </div>
          <div class="d-name" :title="d.title">{{ d.title }}</div>
          <div class="d-meta">
            <span class="price" v-if="d.price">￥{{ d.price }}</span>
            <span class="muted" v-else>价格待采</span>
            <el-tag size="small" type="info" effect="plain" v-if="d.platform">{{ d.platform }}</el-tag>
          </div>
          <div class="annot d-note">点击收录入馆 · 附赠历史价</div>
        </div>
      </div>
      <img class="deco deco-flower-discover" src="/deco/flower-sprig.png" alt="" aria-hidden="true" />
    </div>

    <!-- 标本展位 -->
    <div class="shelf-head">
      <div class="kicker"><span class="pin-dot"></span>SPECIMEN SHELF · 标本展位</div>
      <div class="annot shelf-count">在架标本 {{ total }} 件</div>
    </div>

    <div v-loading="loading" class="grid" ref="gridRef">
      <div
        v-for="(p, i) in items"
        :key="p.id"
        class="item spec-card reveal"
        :data-delay="(i % 6) * 70"
        @click="router.push(`/product/${p.id}`)"
      >
        <span class="pin lot-pin"></span>
        <div class="lot-no">LOT {{ lotNo(i) }}</div>
        <div class="img-wrap">
          <img :src="p.image_url || placeholder" alt="" />
        </div>
        <div class="name" :title="p.name">{{ p.name }}</div>
        <div class="meta">
          <span class="price" v-if="p.min_price" :data-count="p.min_price" data-prefix="￥">￥{{ p.min_price }}</span>
          <span class="muted" v-else>暂无价格</span>
        </div>
        <div class="annot note lead-line">{{ specimenNote(p) }}</div>
      </div>
      <el-empty v-if="!loading && !items.length" description="没有找到相关商品" />
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
      <img class="deco deco-beetle-shelf" src="/deco/beetle.png" alt="" aria-hidden="true" />
    </div>

    <div class="colophon page-foot">PRICE TRACE · 标本手记 —— 每一件商品，都是一枚被记录的价格标本。</div>
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
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20icon%20shopping%20bag%20flat%20design&image_size=square'

const keyword = ref('')
const category = ref('')
const sort = ref('random')
const page = ref(1)
const pageSize = 12
const total = ref(0)
const items = ref<any[]>([])
const categories = ref<any[]>([])
const loading = ref(false)

const realtimeLoading = ref(false)
const realtimeResult = ref<any>(null)

// —— 标本手记动效 ——
const pageRef = ref<HTMLElement | null>(null)
const gridRef = ref<HTMLElement | null>(null)
const titleRef = ref<HTMLElement | null>(null)
const searchBtnRef = ref<HTMLElement | null>(null)

function lotNo(i: number) {
  return String((page.value - 1) * pageSize + i + 1).padStart(3, '0')
}
function specimenNote(p: any) {
  const n = Array.isArray(p.listings) ? p.listings.length : 0
  return n ? `采集自 ${n} 个平台` : '全网采集 · 持续观测'
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
watch(items, async () => {
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

// 搜索栏输入是否为商品链接（触发实时采集）
const isUrlInput = computed(() => /^https?:\/\/\S+$/i.test(keyword.value.trim()))

// 统一提交入口：链接 -> 实时采集；关键词 -> 商品搜索
async function onSubmit() {
  const kw = keyword.value.trim()
  if (!kw) return search(1)
  if (isUrlInput.value) return doRealtime()
  return search(1)
}

async function search(p = 1) {
  page.value = p
  loading.value = true
  try {
    const { data } = await api.get('/api/products/search', {
      params: { keyword: keyword.value, category: category.value, sort: sort.value, page: p, page_size: pageSize },
    })
    items.value = data.items
    total.value = data.total
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

// ---- 野外新采集 ----
const discoverItems = ref<any[]>([])
const discoverLoading = ref(false)
let importingUrl = ''

async function loadDiscover(refresh = 0) {
  discoverLoading.value = true
  try {
    const { data } = await api.get('/api/products/discover', {
      params: { n: 8, refresh },
      timeout: 60000, // 首次需实时爬取，给足超时
    })
    discoverItems.value = data.items
  } catch (e) {
    // 发现失败不影响主搜索
    console.warn('discover failed:', errMsg(e))
  } finally {
    discoverLoading.value = false
    await nextTick()
    rescanReveals(pageRef.value)
  }
}

// 点击新发现商品 -> 收录入库（同步采集历史价） -> 跳详情
async function importProduct(d: any) {
  if (importingUrl) return
  importingUrl = d.url
  const msg = ElMessage({ message: '正在收录并采集历史价格，请稍候…', type: 'info', duration: 0 })
  try {
    const { data } = await api.post(
      '/api/products/import',
      { url: d.url, title: d.title, price: d.price },
      { timeout: 60000 }
    )
    msg.close()
    if (data.ok) {
      ElMessage.success(data.message)
      discoverItems.value = discoverItems.value.filter((x) => x.url !== d.url)
      router.push(`/product/${data.product_id}`)
    }
  } catch (e) {
    msg.close()
    ElMessage.error(errMsg(e))
  } finally {
    importingUrl = ''
  }
}

async function doRealtime() {
  const url = keyword.value.trim()
  realtimeLoading.value = true
  realtimeResult.value = null
  try {
    const { data } = await api.post('/api/products/realtime', { url })
    realtimeResult.value = data
    await nextTick()
    refreshScroll()
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    realtimeLoading.value = false
  }
}

onMounted(() => {
  splitReveal(titleRef.value, 0.05)
  magnetic(searchBtnRef.value)
  if (pageRef.value) revealOnScroll(pageRef.value)
  search(1)
  loadCategories()
  loadDiscover()
})

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
.realtime-result { margin-top: 10px; }

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

/* —— 野外新采集 —— */
.discover-card { margin-bottom: 18px; padding: 18px 20px 74px; }
.d-pin { top: -5px; right: 26px; }
.discover-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px; gap: 12px; }
.head-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.block-title { font-family: var(--serif); font-size: 17px; font-weight: 700; letter-spacing: 0.04em; }
.seal-sm { font-size: 11px; padding: 2px 8px; }
.discover-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 14px; min-height: 120px;
}
.discover-item {
  cursor: pointer;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 10px;
  background: var(--paper-2);
  transition: transform .28s cubic-bezier(0.22, 1, 0.36, 1), box-shadow .28s, border-color .28s;
}
.discover-item:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: var(--green);
}
.d-img {
  position: relative; height: 130px; background: var(--paper-3);
  border: 1px solid var(--line); border-radius: 2px; overflow: hidden;
}
.d-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.d-name {
  margin: 8px 0 6px; font-family: var(--serif); font-size: 13px; line-height: 1.45;
  height: 38px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.d-meta { display: flex; align-items: center; justify-content: space-between; }
.d-note { font-size: 11px; margin-top: 6px; opacity: 0.55; transition: opacity .25s; }
.discover-item:hover .d-note { opacity: 1; }

/* —— 标本展位 —— */
.shelf-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin: 4px 2px 12px;
  border-bottom: 1px dashed var(--line-strong);
  padding-bottom: 8px;
}
.shelf-count { font-size: 12px; }
.grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 16px; min-height: 200px;
}
.item {
  cursor: pointer;
  padding: 12px 14px 12px;
  transition: transform .18s, box-shadow .18s;
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
  height: 160px;
  display: flex; align-items: center; justify-content: center;
  background: var(--paper-3);
  border: 1px solid var(--line);
  border-radius: 2px;
  box-shadow: inset 0 0 0 3px var(--paper-2);
  overflow: hidden;
  padding: 8px;
}
.img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
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
.deco-fern-head { width: 110px; top: -6px; right: 2px; opacity: 0.75; transform: rotate(10deg); }
.deco-flower-discover { width: 90px; right: -14px; bottom: -18px; opacity: 0.8; transform: rotate(8deg); }
.deco-beetle-shelf { width: 80px; top: -12px; right: 4px; opacity: 0.7; transform: rotate(-8deg); }

@media (max-width: 1280px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
  .idx-sort { margin-left: 0; }
}
</style>
