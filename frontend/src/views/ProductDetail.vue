<template>
  <div class="page" v-loading="loading" ref="pageRef">
    <template v-if="product">
      <!-- 标本铭牌 -->
      <div class="spec-card head reveal">
        <span class="tape h-tl"></span>
        <span class="pin head-pin" ref="headPinRef"></span>
        <img class="deco deco-wax-seal" ref="sealRef" src="/deco/wax-seal.png" alt="" aria-hidden="true" />
        <div class="cover-mat">
          <img class="cover" :src="product.image_url || placeholder" alt="" />
        </div>
        <div class="info">
          <div class="kicker"><span class="pin-dot"></span>SPECIMEN No.{{ specimenNo }} · PLATE Ⅳ</div>
          <h1 class="spec-name" ref="nameRef">{{ product.name }}</h1>
          <div class="plate-meta">
            <span class="mono-tag">COLLECTED {{ collectedAt || '—' }}</span>
            <span class="mono-tag">{{ product.category || '未分类' }} · {{ product.brand || '未知品牌' }}</span>
          </div>
          <div class="price-block">
            <div class="kicker">LOWEST ON RECORD · 全平台最低价</div>
            <div class="big-price price" v-if="product.min_price != null" :data-count="product.min_price" data-prefix="￥">
              ￥{{ product.min_price }}
            </div>
            <div class="big-price muted" v-else>--</div>
            <div class="annot price-note lead-line" v-if="gapNote">{{ gapNote }}</div>
            <div class="price-tag">
              <img src="/deco/paper-tag.png" alt="" aria-hidden="true" />
              <span class="tag-text">史低 ￥{{ trend?.min_price ?? '—' }}</span>
            </div>
          </div>
          <div class="actions">
            <span class="magnetic btn-magnet" ref="trackBtnRef">
              <el-button type="primary" @click="trackDialog = true">
                <el-icon style="margin-right: 4px"><Timer /></el-icon>加入价格追踪
              </el-button>
            </span>
            <span class="magnetic btn-magnet" ref="compareBtnRef">
              <el-button @click="router.push(`/compare?ids=${product.id}`)">多平台比价</el-button>
            </span>
          </div>
          <!-- AI 导购快捷输入口：带商品信息 + 问题跳转聊天 -->
          <div class="ask-bar">
            <el-input
              v-model="askQuestion"
              placeholder="向 AI 导购提问，如：现在值得买吗？（回车发送）"
              clearable
              @keyup.enter="goAdvisor"
            >
              <template #prefix>
                <el-icon color="#3c5a45"><MagicStick /></el-icon>
              </template>
            </el-input>
            <el-button type="success" @click="goAdvisor">
              问 AI 导购
              <el-icon style="margin-left: 4px"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 采集点比价 -->
      <div class="spec-card sites-card reveal" data-delay="80">
        <div class="kicker"><span class="pin-dot"></span>SPECIMEN SITES · 采集点</div>
        <div class="block-title">同一件标本，{{ product.listings.length }} 个采集点</div>
        <div class="site-list">
          <div class="site-row" v-for="row in product.listings" :key="row.id">
            <span class="site-plat"><el-tag size="small">{{ platformName(row.platform) }}</el-tag></span>
            <span class="site-title" :title="row.title">{{ row.title }}</span>
            <div class="site-bar"><i :style="{ width: barWidth(row) }"></i></div>
            <b class="price site-price">￥{{ row.current_price }}</b>
            <span class="seal seal-sm site-low" v-if="isLowest(row)">史低</span>
            <span class="muted site-time">{{ row.last_crawled_at || '未采集' }}</span>
            <el-link v-if="row.url" :href="row.url" target="_blank" type="primary">前往购买</el-link>
          </div>
          <el-empty v-if="!product.listings.length" description="暂无采集点" :image-size="60" />
        </div>
      </div>

      <!-- 价格呼吸图谱 -->
      <div class="spec-card chart-card reveal" data-delay="140">
        <div class="row">
          <div>
            <div class="kicker"><span class="pin-dot"></span>PRICE RESPIRATION PLATE</div>
            <div class="block-title">价格呼吸图谱</div>
          </div>
          <el-radio-group v-model="days" size="small" @change="loadTrend">
            <el-radio-button :label="30">近 30 天</el-radio-button>
            <el-radio-button :label="90">近 90 天</el-radio-button>
            <el-radio-button :label="180">近 180 天</el-radio-button>
            <el-radio-button :label="365">近一年</el-radio-button>
          </el-radio-group>
        </div>
        <div class="annot chart-note lead-line">图注：曲线取每日最低采集价，朱砂圆点标记史低，虚线为当前价水平线。</div>
        <div class="stats" v-if="trend">
          <div class="stat"><div class="label">当前价</div><div class="value price">￥{{ trend.current_price ?? '--' }}</div></div>
          <div class="stat min"><div class="label">{{ days }} 天最低</div><div class="value">￥{{ trend.min_price ?? '--' }}</div></div>
          <div class="stat max"><div class="label">{{ days }} 天最高</div><div class="value">￥{{ trend.max_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">平均价</div><div class="value">￥{{ trend.avg_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">数据点</div><div class="value">{{ trend.points.length }} 天</div></div>
        </div>
        <PriceTrendChart :points="trend?.points || []" :title="`历史价格走势（近 ${days} 天）`" style="margin-top: 8px" />
        <img class="deco deco-fern-chart" src="/deco/fern-sprig.png" alt="" aria-hidden="true" />
      </div>
    </template>

    <el-dialog v-model="trackDialog" title="加入价格追踪" width="420px">
      <div style="margin-bottom: 12px" class="muted">
        设置目标价后，当「{{ product?.name }}」价格达到目标价时系统会向你推送降价提醒。
      </div>
      <el-input-number v-model="targetPrice" :min="0" :precision="2" :step="10" style="width: 200px" />
      <template #footer>
        <el-button @click="trackDialog = false">取消</el-button>
        <el-button type="primary" :loading="trackLoading" @click="addTracking">确定追踪</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import api, { errMsg } from '../api'
import PriceTrendChart from '../components/PriceTrendChart.vue'
import { splitReveal, revealOnScroll, refreshScroll, countUp, magnetic, popIn, pinPress } from '../anim'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20shopping%20bag%20flat%20design&image_size=square'

const loading = ref(false)
const product = ref<any>(null)
const trend = ref<any>(null)
const days = ref(180)

const trackDialog = ref(false)
const askQuestion = ref('')  // AI 导购快捷提问
const targetPrice = ref<number | undefined>(undefined)
const trackLoading = ref(false)

// —— 标本手记动效 ——
const pageRef = ref<HTMLElement | null>(null)
const nameRef = ref<HTMLElement | null>(null)
const sealRef = ref<HTMLElement | null>(null)
const headPinRef = ref<HTMLElement | null>(null)
const trackBtnRef = ref<HTMLElement | null>(null)
const compareBtnRef = ref<HTMLElement | null>(null)

// —— 铭牌展示信息（纯展示派生，不动数据逻辑） ——
const specimenNo = computed(() => String(id).padStart(3, '0'))
const collectedAt = computed(() => {
  const pts = trend.value?.points
  return Array.isArray(pts) && pts.length ? pts[0].date : ''
})
const gapNote = computed(() => {
  const t = trend.value
  if (!t || t.min_price == null) return ''
  const cur = t.current_price ?? product.value?.min_price
  if (cur == null) return ''
  const diff = Math.round((cur - t.min_price) * 100) / 100
  return diff <= 0 ? '已抵史低，正是入手时机' : `距史低 ￥${diff}，可观望，亦可入手`
})
const maxListingPrice = computed(() => {
  const ls = product.value?.listings || []
  return ls.reduce((m: number, r: any) => Math.max(m, r.current_price || 0), 0)
})
function barWidth(row: any) {
  const max = maxListingPrice.value
  if (!max || row.current_price == null) return '0%'
  return Math.max(6, Math.round((row.current_price / max) * 100)) + '%'
}
function isLowest(row: any) {
  const ls = product.value?.listings || []
  if (!ls.length || row.current_price == null) return false
  return row.current_price === Math.min(...ls.map((r: any) => r.current_price ?? Infinity))
}

const names: Record<string, string> = {
  jd: '京东', taobao: '淘宝', manmanbuy: '慢慢买', dangdang: '当当',
  suning: '苏宁', pdd: '拼多多', vip: '唯品会', web: '其他',
}
const platformName = (p: string) => names[p] || p

async function load() {
  loading.value = true
  try {
    const [{ data: p }, { data: t }] = await Promise.all([
      api.get(`/api/products/${id}`),
      api.get(`/api/tracking/trend/${id}`, { params: { days: days.value } }),
    ])
    product.value = p
    trend.value = t
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}
async function loadTrend() {
  const { data } = await api.get(`/api/tracking/trend/${id}`, { params: { days: days.value } })
  trend.value = data
}
async function addTracking() {
  trackLoading.value = true
  try {
    const { data } = await api.post('/api/tracking', {
      product_id: id,
      target_price: targetPrice.value ?? null,
    })
    ElMessage.success(data.message)
    trackDialog.value = false
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    trackLoading.value = false
  }
}
// 快捷输入口：带当前商品 + 问题跳转 AI 导购聊天页
function goAdvisor() {
  const q = askQuestion.value.trim()
  const base = `/advisor?product=${id}`
  router.push(q ? `${base}&q=${encodeURIComponent(q)}` : base)
}

// 异步内容到位后编排动效
async function animate() {
  await nextTick()
  splitReveal(nameRef.value, 0.1)
  popIn(sealRef.value, 0.55)
  pinPress(headPinRef.value, 0.15)
  magnetic(trackBtnRef.value)
  magnetic(compareBtnRef.value)
  const big = pageRef.value?.querySelector<HTMLElement>('.big-price[data-count]')
  if (big && Number.isInteger(parseFloat(big.dataset.count || ''))) countUp(big)
  if (pageRef.value) revealOnScroll(pageRef.value)
  refreshScroll()
}

onMounted(async () => {
  await load()
  animate()
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
/* —— 标本铭牌 —— */
.head { display: flex; gap: 22px; padding: 24px 26px; }
.tape { position: absolute; }
.h-tl { top: -8px; left: 30px; transform: rotate(-4deg); }
.head-pin { top: -5px; left: 50%; margin-left: -5px; }
.cover-mat {
  width: 232px; height: 232px; flex: none;
  display: flex; align-items: center; justify-content: center;
  background: var(--paper-3);
  border: 1px solid var(--line);
  border-radius: 2px;
  box-shadow: inset 0 0 0 4px var(--paper-2);
  padding: 12px;
}
.cover { max-width: 100%; max-height: 100%; object-fit: contain; }
.info { flex: 1; min-width: 0; position: relative; }
.spec-name {
  font-family: var(--serif);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.03em;
  line-height: 1.35;
  margin: 8px 0 10px;
}
.plate-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mono-tag {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--ink-faint);
  border: 1px solid var(--line); border-radius: 2px;
  padding: 3px 8px;
}
.seal-sm { font-size: 11px; padding: 2px 8px; }
.price-block { position: relative; margin-top: 16px; }
.big-price {
  font-family: var(--mono); font-size: 34px; font-weight: 700;
  letter-spacing: 0.01em; line-height: 1.2; margin-top: 6px;
}
.big-price.muted { font-size: 22px; }
.price-note { font-size: 12px; margin-top: 8px; max-width: 420px; }
.actions { margin-top: 16px; display: flex; gap: 10px; align-items: center; }
.btn-magnet { display: inline-flex; }
.ask-bar { display: flex; gap: 10px; margin-top: 12px; max-width: 520px; }
.ask-bar .el-input { flex: 1; }

/* —— 采集点比价 —— */
.sites-card { margin-top: 16px; padding: 20px 22px; }
.block-title {
  font-family: var(--serif); font-size: 17px; font-weight: 700;
  letter-spacing: 0.04em; margin-top: 4px;
}
.site-list { margin-top: 14px; }
.site-row {
  display: flex; align-items: center; gap: 14px;
  padding: 11px 10px;
  border-bottom: 1px dashed var(--line);
  transition: background 0.25s;
}
.site-row:last-of-type { border-bottom: none; }
.site-row:hover { background: rgba(60, 90, 69, 0.05); }
.site-plat { flex: none; width: 76px; }
.site-title {
  flex: 1; min-width: 0; font-size: 13px; color: var(--ink-soft);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.site-bar {
  flex: none; width: 170px; height: 10px;
  background: var(--paper-3);
  border: 1px solid var(--line);
  border-radius: 2px;
  overflow: hidden;
}
.site-bar i {
  display: block; height: 100%;
  background: var(--green);
  opacity: 0.75;
}
.site-price { flex: none; width: 92px; text-align: right; font-size: 15px; }
.site-low { flex: none; }
.site-time { flex: none; width: 150px; text-align: right; }

/* —— 价格呼吸图谱 —— */
.chart-card { margin-top: 16px; padding: 20px 22px; }
.row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.chart-note { font-size: 12px; margin-top: 10px; }
.stats { display: flex; gap: 28px; margin: 16px 0 4px; flex-wrap: wrap; }
.stat .label { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--ink-faint); }
.stat .value { font-family: var(--mono); font-size: 18px; font-weight: 700; margin-top: 4px; }
.stat.min .value { color: var(--green); }
.stat.max .value { color: var(--pin); }

/* —— 透明装饰素材 —— */
.deco { position: absolute; pointer-events: none; z-index: 3; }
.deco-wax-seal { width: 80px; top: -30px; right: 20px; transform: rotate(-10deg); }
.price-tag {
  position: absolute;
  top: -6px; right: 10px; width: 110px;
  pointer-events: none; transform: rotate(8deg); z-index: 3;
}
.price-tag img { width: 100%; display: block; }
.tag-text {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  padding: 42px 10px 4px 34px;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.02em;
  color: var(--ink); white-space: nowrap;
}
.deco-fern-chart { width: 100px; right: 8px; bottom: -22px; opacity: 0.7; transform: rotate(-8deg); }

@media (max-width: 1280px) {
  .head { flex-wrap: wrap; }
  .cover-mat { width: 200px; height: 200px; }
  .site-bar { width: 110px; }
  .site-time { width: 120px; }
}
</style>
