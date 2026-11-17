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
      <div class="annot shelf-count">在架标本 {{ total }} 件 · 实时来自慢慢买</div>
    </div>

    <div v-loading="loading" element-loading-text="标本采集中" class="grid" ref="gridRef">
      <div
        v-for="(p, i) in displayItems"
        :key="p.url"
        class="item spec-card reveal"
        :data-delay="(i % 6) * 70"
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
const allItems = ref<any[]>([])
const categories = ref<any[]>([])
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
      params: { keyword: keyword.value.trim(), category: category.value, n: 24 },
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
.grid {
  display: grid; grid-template-columns: repeat(6, 1fr);
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
.deco-magnifier-head { width: 95px; top: -6px; right: 2px; opacity: 0.8; transform: rotate(-8deg); }
.deco-maple-shelf { width: 95px; top: -12px; right: 4px; opacity: 0.8; transform: rotate(10deg); }

@media (max-width: 1280px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
  .idx-sort { margin-left: 0; }
}
</style>
