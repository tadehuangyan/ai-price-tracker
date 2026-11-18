<template>
  <div class="page compare" ref="rootEl">
    <header class="page-head">
      <img src="/deco/pine-cone.png" alt="" aria-hidden="true" class="deco deco-flower" />
      <div class="kicker"><span class="pin-dot"></span>PLATFORM SPREAD · 比价台</div>
      <h1 class="page-title" ref="titleEl">价格对比 · 比价台</h1>
      <p class="page-sub">同物异价，列而观之；平台散布如星，取其低者而录之。</p>
    </header>

    <!-- —— 标本上台 · 对比项添加区 —— -->
    <section class="spec-card stage reveal" data-delay="100">
      <div class="tape stage-tape"></div>
      <div class="kicker"><span class="pin-dot"></span>BENCH · 标本上台</div>
      <!-- 统一添加入口：输入商品名搜索 / 粘贴链接自动收录加入 -->
      <div class="stage-row stage-adds">
        <el-select
          :key="selectKey"
          v-model="selected"
          multiple
          filterable
          remote
          reserve-keyword
          :remote-method="searchProducts"
          :loading="searching"
          placeholder="搜索商品名或粘贴商品链接，回车添加（1~5 个）"
          class="add-select"
          :multiple-limit="5"
        >
          <el-option v-for="o in options" :key="o.id" :value="o.id" :label="o.name" />
        </el-select>
        <el-popover placement="bottom-end" :width="360" trigger="click" v-model:visible="favVisible">
          <template #reference>
            <el-button class="mag-btn">＋ 收藏商品</el-button>
          </template>
          <div class="fav-list">
            <div class="panel-title">价格追踪（收藏栏）· 点击加入对比</div>
            <div v-for="t in trackings" :key="t.id" class="fav-item" @click="addFromFav(t)">
              <img :src="t.image_url || placeholder" class="fav-img" />
              <div class="fav-info">
                <div class="fav-name">{{ t.product_name }}</div>
                <div class="fav-price">
                  <span v-if="t.current_price" class="price">￥{{ t.current_price }}</span>
                  <span v-if="t.target_price" class="muted">目标 ￥{{ t.target_price }}</span>
                </div>
              </div>
              <el-button size="small" type="primary" plain round>加入</el-button>
            </div>
            <el-empty v-if="!trackings.length" description="暂无收藏商品" :image-size="50" />
          </div>
        </el-popover>
      </div>
      <div class="stage-row stage-actions">
        <div class="picker">
          <el-radio-group v-model="days" size="default" class="days-group">
            <el-radio-button :label="30">30 天</el-radio-button>
            <el-radio-button :label="90">90 天</el-radio-button>
            <el-radio-button :label="180">180 天</el-radio-button>
            <el-radio-button :label="365">一年</el-radio-button>
          </el-radio-group>
        </div>
        <el-button
          class="mag-btn"
          type="primary"
          :loading="loading"
          @click="doCompare"
          :disabled="!selected.length"
        >
          开始对比
        </el-button>
      </div>
      <p class="annot stage-note">选 1~5 件标本置于台上，同台列价，一观高下。</p>
    </section>

    <!-- 空态：比价台空置 -->
    <div v-if="!result" class="empty-stage reveal" data-delay="160">
      <span class="pin empty-pin" ref="emptyPinEl"></span>
      <img src="/deco/paper-tag.png" alt="" aria-hidden="true" class="deco deco-tag" />
      <div class="empty-frame">
        <p class="annot empty-note">比价台空置</p>
        <p class="muted">搜索并选定商品后，按「开始对比」陈列比价</p>
      </div>
    </div>

    <template v-else>
      <!-- —— 全网比价图谱 —— -->
      <section class="spec-card chart-card reveal" data-delay="80">
        <div class="tape chart-tape"></div>
        <div class="board-head">
          <div>
            <div class="kicker"><span class="pin-dot"></span>FIG. 01 · 图谱</div>
            <h2 class="board-title">全网比价图谱</h2>
          </div>
          <span class="colophon">当前最低价 × 历史最低价</span>
        </div>
        <div ref="barEl" class="bar-box"></div>
        <p class="annot fig-note">柱高即价：深绿为当下全网之最低，赭红为其历史低点。</p>
      </section>

      <!-- —— 检验单：多平台比价明细 —— -->
      <section class="spec-card sheet-card reveal" data-delay="140">
        <div class="board-head">
          <div>
            <div class="kicker"><span class="pin-dot"></span>FIG. 02 · 检验单</div>
            <h2 class="board-title">同款多平台比价明细</h2>
          </div>
          <span class="colophon">INSPECTION SHEET · {{ pad(result.products.length) }} ENTRIES</span>
        </div>
        <el-table :data="result.products" border>
          <el-table-column label="NO." width="72">
            <template #default="{ index }">
              <span class="row-no">No.{{ pad(index + 1) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="product_name" label="商品" min-width="210" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="prod-name">{{ row.product_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="平台报价" min-width="310">
            <template #default="{ row }">
              <div v-for="(o, i) in row.offers" :key="o.platform" class="offer-line">
                <span class="offer-no">{{ pad2(i + 1) }}</span>
                <span class="offer-platform">{{ o.platform }}</span>
                <b class="offer-price" :class="{ 'is-lowest': i === 0 }"
                  ><span
                    class="cnt"
                    :key="`off-${row.product_name}-${o.platform}-${o.price}`"
                    :data-count="parts(o.price)[0]"
                    data-prefix="￥"
                  ></span
                  ><span v-if="parts(o.price)[1]" class="dec">{{ parts(o.price)[1] }}</span></b
                >
                <span v-if="i === 0" class="seal seal-low">最低</span>
                <el-link v-if="o.url" :href="o.url" target="_blank" type="primary" class="offer-link">链接</el-link>
              </div>
              <span v-if="!row.offers.length" class="muted">暂无报价</span>
            </template>
          </el-table-column>
          <el-table-column label="最大差价" width="140">
            <template #default="{ row }">
              <b v-if="row.diff != null" class="diff-num"
                ><span class="pin pin-inline"></span
                ><span
                  class="cnt"
                  :key="`diff-${row.product_name}-${row.diff}`"
                  :data-count="parts(row.diff)[0]"
                  data-prefix="￥"
                ></span
                ><span v-if="parts(row.diff)[1]" class="dec">{{ parts(row.diff)[1] }}</span></b
              >
              <span v-else class="muted">--</span>
            </template>
          </el-table-column>
          <el-table-column label="历史最低 / 当前" width="210">
            <template #default="{ row }">
              <div class="min-line">
                <div class="min-block">
                  <div class="kicker min-label">LOW · 史低</div>
                  <b v-if="row.history_min != null" class="hist-num"
                    ><span
                      class="cnt"
                      :key="`h-${row.product_name}-${row.history_min}`"
                      :data-count="parts(row.history_min)[0]"
                      data-prefix="￥"
                    ></span
                    ><span v-if="parts(row.history_min)[1]" class="dec">{{ parts(row.history_min)[1] }}</span></b
                  >
                  <span v-else class="muted">--</span>
                </div>
                <div class="min-block">
                  <div class="kicker min-label">NOW · 当前</div>
                  <b v-if="row.current_min != null" class="big-num"
                    ><span
                      class="cnt"
                      :key="`n-${row.product_name}-${row.current_min}`"
                      :data-count="parts(row.current_min)[0]"
                      data-prefix="￥"
                    ></span
                    ><span v-if="parts(row.current_min)[1]" class="dec">{{ parts(row.current_min)[1] }}</span></b
                  >
                  <span v-else class="muted">--</span>
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <!-- —— 走势对比 —— -->
      <section class="spec-card trend-card reveal" data-delay="180">
        <div class="board-head">
          <div>
            <div class="kicker"><span class="pin-dot"></span>FIG. 03 · 走势</div>
            <h2 class="board-title">历史价格走势对比（近 {{ days }} 天）</h2>
          </div>
          <span class="colophon">SPECIMEN CURVES</span>
        </div>
        <PriceTrendChart :points="[]" :compare-series="compareSeriesComp" :height="340" />
        <p class="annot fig-note">折线起伏，即价之涨落；同图而观，高下立判。</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import api, { errMsg } from '../api'
import PriceTrendChart from '../components/PriceTrendChart.vue'
import { splitReveal, revealOnScroll, countUp, magnetic, pinPress, refreshScroll } from '../anim'

const route = useRoute()
const selected = ref<number[]>([])
const options = ref<any[]>([])
const searching = ref(false)
const days = ref(180)
const loading = ref(false)
const result = ref<any>(null)
const barEl = ref<HTMLDivElement>()
let barChart: echarts.ECharts | null = null

// —— 统一添加入口：搜索 / 链接收录 / 收藏商品 ——
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20shopping%20bag%20flat%20design&image_size=square'
const selectKey = ref(0) // 收录完成后重置输入框（清掉已粘贴的链接文本）
const favVisible = ref(false)
const trackings = ref<any[]>([])

function pushSelected(pid: number, name: string) {
  if (!pid) return
  if (selected.value.includes(pid)) {
    ElMessage.info('该商品已在对比台上')
    return
  }
  if (selected.value.length >= 5) {
    ElMessage.warning('单次最多对比 5 个商品')
    return
  }
  if (!options.value.some((o) => o.id === pid)) options.value.push({ id: pid, name })
  selected.value.push(pid)
}

// 粘贴链接 -> 后台静默收录入库（实时爬取慢慢买）-> 自动加入对比台
async function importLink(url: string) {
  searching.value = true
  try {
    const { data } = await api.post('/api/products/import', { url }, { timeout: 60000 })
    let name = `商品 #${data.product_id}`
    try {
      const { data: p } = await api.get(`/api/products/${data.product_id}`)
      name = p.name || name
    } catch {
      /* 名称取不到时用兜底标签 */
    }
    pushSelected(data.product_id, name)
    ElMessage.success(data.message || '已收录并加入对比')
    selectKey.value++ // 重置输入框，清掉已粘贴的链接文本
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    searching.value = false
  }
}

// 收藏商品（价格追踪）-> 直接加入对比台
function addFromFav(t: any) {
  favVisible.value = false
  pushSelected(t.product_id, t.product_name)
}

async function loadTrackings() {
  try {
    const { data } = await api.get('/api/tracking')
    trackings.value = data
  } catch {
    /* 未登录等情况忽略 */
  }
}

const rootEl = ref<HTMLDivElement | null>(null)
const titleEl = ref<HTMLHeadingElement | null>(null)
const emptyPinEl = ref<HTMLSpanElement | null>(null)

// —— 检验单排版工具 ——
const pad = (n: number) => String(n).padStart(3, '0')
const pad2 = (n: number) => String(n).padStart(2, '0')
/** 拆整数/小数：整数交给 countUp，小数静态展示，保证金额不失真 */
function parts(v: unknown): [number, string] {
  const n = Number(v)
  if (!Number.isFinite(n)) return [0, '']
  const int = Math.trunc(n)
  const dec = Math.abs(n - int).toFixed(2).slice(1)
  return [int, dec === '.00' ? '' : dec]
}

// —— 动效编排（副作用统一在此清理） ——
const magnetized = new WeakSet<Element>()
function magnet(el: HTMLElement | null | undefined) {
  if (!el || magnetized.has(el)) return
  magnetized.add(el)
  magnetic(el)
}
let ownedTriggers: ScrollTrigger[] = []
function playReveal(root: ParentNode) {
  const before = new Set(ScrollTrigger.getAll())
  revealOnScroll(root)
  ownedTriggers.push(...ScrollTrigger.getAll().filter((t) => !before.has(t)))
}
function playCounts() {
  rootEl.value?.querySelectorAll<HTMLElement>('.cnt:not([data-counted])').forEach((el) => countUp(el))
}
async function playPage() {
  await nextTick()
  playCounts()
  playReveal(rootEl.value ?? document)
  rootEl.value?.querySelectorAll<HTMLElement>('.mag-btn').forEach((el) => magnet(el))
  refreshScroll()
}

// 统一输入入口：商品链接 -> 静默收录并加入；关键词 -> 远程搜索
async function searchProducts(q: string) {
  const kw = q.trim()
  if (!kw) return
  if (/^https?:\/\//i.test(kw)) {
    await importLink(kw)
    return
  }
  searching.value = true
  try {
    const { data } = await api.get('/api/products/search', { params: { keyword: kw, page_size: 20 } })
    options.value = data.items
  } finally {
    searching.value = false
  }
}

async function doCompare() {
  loading.value = true
  try {
    const { data } = await api.post('/api/compare', { product_ids: selected.value, days: days.value })
    result.value = data
    await nextTick()
    renderBar(data)
    await playPage()
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

function renderBar(data: any) {
  if (!barEl.value) return
  barChart = barChart || echarts.init(barEl.value)
  const names = data.products.map((p: any) => p.product_name)
  const lowest = data.products.map((p: any) => p.current_min)
  const histMin = data.products.map((p: any) => p.history_min)
  barChart.setOption(
    {
      tooltip: { trigger: 'axis', valueFormatter: (v: any) => (v == null ? '-' : '￥' + v) },
      legend: { top: 0, textStyle: { color: '#5c5546' } },
      grid: { left: 60, right: 20, top: 40, bottom: 60 },
      xAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: '#b9aa8e' } },
        axisTick: { lineStyle: { color: '#b9aa8e' } },
        axisLabel: {
          interval: 0,
          rotate: names.some((n: string) => n.length > 8) ? 20 : 0,
          width: 110,
          overflow: 'truncate',
          color: '#5c5546',
        },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: '￥{value}', color: '#8d8574' },
        splitLine: { lineStyle: { color: 'rgba(185, 170, 142, 0.35)', type: 'dashed' } },
      },
      series: [
        { name: '当前最低价', type: 'bar', data: lowest, itemStyle: { color: '#3c5a45' }, barMaxWidth: 46 },
        { name: '历史最低价', type: 'bar', data: histMin, itemStyle: { color: '#b0603c' }, barMaxWidth: 46 },
      ],
    },
    true
  )
}

const compareSeriesComp = computed(() =>
  (result.value?.products || []).map((p: any) => ({ name: p.product_name, data: p.series }))
)

// 从 URL 直接带入商品（商品页“多平台比价”入口）
onMounted(async () => {
  splitReveal(titleEl.value, 0.12)
  await playPage()
  if (!result.value) pinPress(emptyPinEl.value)
  loadTrackings()
  const ids = route.query.ids
  if (ids) {
    selected.value = String(ids).split(',').map(Number).filter(Boolean)
    if (selected.value.length) doCompare()
  }
})
onUnmounted(() => {
  ownedTriggers.forEach((t) => t.kill())
  ownedTriggers = []
})
</script>

<style scoped>
/* —— 页头 —— */
.page-head { position: relative; }
.page-title { font-size: 30px; }

/* —— 透明装饰素材（标本点缀，纯表现层） —— */
.deco { position: absolute; pointer-events: none; user-select: none; z-index: 2; }
.deco-flower {
  width: 90px; right: 6px; top: -8px;
  transform: rotate(-7deg); opacity: 0.75;
}
.deco-tag {
  width: 90px; right: 30px; top: -18px;
  transform: rotate(9deg); opacity: 0.9;
}

/* —— 通用板 —— */
.board-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.board-title {
  font-family: var(--serif);
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin: 5px 0 0;
  color: var(--ink);
}
.fig-note { margin: 10px 0 0; font-size: 12.5px; line-height: 1.8; }

/* —— 标本上台 操作条 —— */
.stage { padding: 20px 26px 18px; margin-bottom: 18px; }
.stage-tape { top: -11px; right: 64px; transform: rotate(1.8deg); }
.stage-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.picker { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.days-group { margin-left: 0; }
.stage-note { margin: 12px 0 0; font-size: 12.5px; }

/* —— 统一添加入口行：搜索 / 链接 / 收藏 —— */
.stage-adds { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stage-adds :deep(.add-select) { flex: 1; min-width: 320px; }
.stage-actions { margin-top: 12px; }
.fav-list { max-height: 280px; overflow-y: auto; }
.panel-title {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--ink-faint); margin-bottom: 8px; text-transform: uppercase;
}
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

/* —— 空态：比价台空置 —— */
.empty-stage { position: relative; padding: 28px 22px 26px; }
.empty-pin { top: 12px; left: 50%; margin-left: -5px; }
.empty-frame {
  border: 1px dashed var(--line-strong);
  border-radius: 2px;
  padding: 34px 20px;
  text-align: center;
}
.empty-note {
  font-size: 17px;
  letter-spacing: 0.22em;
  color: var(--ink-soft);
  margin: 0 0 8px;
}

/* —— 图谱卡 —— */
.chart-card { padding: 22px 26px 20px; margin-bottom: 18px; }
.chart-tape { top: -11px; left: 52px; transform: rotate(-1.4deg); }
.bar-box { height: 320px; width: 100%; }

/* —— 检验单 —— */
.sheet-card { padding: 22px 26px 24px; margin-bottom: 18px; }
.sheet-card:hover { transform: none; box-shadow: var(--shadow-md); }
.row-no {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--ink-faint);
}
.prod-name {
  font-family: var(--serif);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--ink);
}
.offer-line { display: flex; align-items: center; gap: 10px; padding: 3px 0; }
.offer-no {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-faint);
}
.offer-platform {
  font-family: var(--serif);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--ink);
  min-width: 44px;
}
.offer-price {
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-soft);
  white-space: nowrap;
}
.offer-price.is-lowest { color: var(--pin); font-size: 15px; }
.offer-link { margin-left: 2px; }
.seal-low {
  font-size: 11px;
  padding: 1px 7px;
  letter-spacing: 0.16em;
  color: var(--green);
  border-color: var(--green);
  background: var(--green-soft);
  transform: rotate(-3deg);
}
.dec { font-size: 11px; }
.diff-num {
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 700;
  color: var(--pin);
  white-space: nowrap;
}
.pin.pin-inline {
  position: static;
  display: inline-block;
  margin-right: 6px;
  vertical-align: 1px;
}
.min-line { display: flex; align-items: center; gap: 18px; }
.min-block { min-width: 0; }
.min-label { margin-bottom: 3px; }
.hist-num {
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--green);
  white-space: nowrap;
}
.big-num {
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 700;
  color: var(--pin);
  white-space: nowrap;
}

/* —— 走势卡 —— */
.trend-card { padding: 22px 26px 20px; }

@media (max-width: 1320px) {
  .offer-platform { min-width: 38px; }
}
</style>
