<template>
  <div class="page">
    <div class="card">
      <div class="row">
        <div class="picker">
          <el-select
            v-model="selected"
            multiple
            filterable
            remote
            reserve-keyword
            :remote-method="searchProducts"
            :loading="searching"
            placeholder="搜索并选择 1~5 个商品进行对比"
            style="width: 560px"
            :multiple-limit="5"
          >
            <el-option v-for="o in options" :key="o.id" :value="o.id" :label="o.name" />
          </el-select>
          <el-radio-group v-model="days" size="default" style="margin-left: 12px">
            <el-radio-button :label="30">30 天</el-radio-button>
            <el-radio-button :label="90">90 天</el-radio-button>
            <el-radio-button :label="180">180 天</el-radio-button>
            <el-radio-button :label="365">一年</el-radio-button>
          </el-radio-group>
        </div>
        <el-button type="primary" :loading="loading" @click="doCompare" :disabled="!selected.length">
          开始对比
        </el-button>
      </div>
    </div>

    <template v-if="result">
      <div class="card" style="margin-top: 16px">
        <h3 class="page-title" style="margin-bottom: 4px">当前价格对比（最低价已标绿）</h3>
        <div ref="barEl" style="height: 320px; width: 100%"></div>
      </div>

      <div class="card" style="margin-top: 16px">
        <h3 class="page-title" style="margin-bottom: 8px">同款多平台比价明细</h3>
        <el-table :data="result.products" border>
          <el-table-column prop="product_name" label="商品" min-width="220" show-overflow-tooltip />
          <el-table-column label="平台报价" min-width="300">
            <template #default="{ row }">
              <div v-for="(o, i) in row.offers" :key="o.platform" class="offer-line">
                <el-tag size="small" :type="i === 0 ? 'success' : 'info'" effect="plain">{{ o.platform }}</el-tag>
                <b :class="{ price: i === 0 }" :style="i === 0 ? '' : 'color:#606266'">￥{{ o.price }}</b>
                <el-link v-if="o.url" :href="o.url" target="_blank" type="primary" style="margin-left: 8px">链接</el-link>
              </div>
              <span v-if="!row.offers.length" class="muted">暂无报价</span>
            </template>
          </el-table-column>
          <el-table-column label="最大差价" width="120">
            <template #default="{ row }"><b style="color: #e6a23c">￥{{ row.diff }}</b></template>
          </el-table-column>
          <el-table-column label="历史最低 / 当前" width="180">
            <template #default="{ row }">
              <span style="color: #67c23a">￥{{ row.history_min ?? '--' }}</span>
              <span class="muted"> / </span>
              <span class="price">￥{{ row.current_min ?? '--' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="card" style="margin-top: 16px">
        <h3 class="page-title" style="margin-bottom: 4px">历史价格走势对比（近 {{ days }} 天）</h3>
        <PriceTrendChart :points="[]" :compare-series="compareSeriesComp" :height="340" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api, { errMsg } from '../api'
import PriceTrendChart from '../components/PriceTrendChart.vue'

const route = useRoute()
const selected = ref<number[]>([])
const options = ref<any[]>([])
const searching = ref(false)
const days = ref(180)
const loading = ref(false)
const result = ref<any>(null)
const barEl = ref<HTMLDivElement>()
let barChart: echarts.ECharts | null = null

async function searchProducts(q: string) {
  if (!q) return
  searching.value = true
  try {
    const { data } = await api.get('/api/products/search', { params: { keyword: q, page_size: 20 } })
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
      legend: { top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: names.some((n: string) => n.length > 8) ? 20 : 0, width: 110, overflow: 'truncate' } },
      yAxis: { type: 'value', axisLabel: { formatter: '￥{value}' } },
      series: [
        { name: '当前最低价', type: 'bar', data: lowest, itemStyle: { color: '#409eff' }, barMaxWidth: 46 },
        { name: '历史最低价', type: 'bar', data: histMin, itemStyle: { color: '#67c23a' }, barMaxWidth: 46 },
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
  const ids = route.query.ids
  if (ids) {
    selected.value = String(ids).split(',').map(Number).filter(Boolean)
    if (selected.value.length) doCompare()
  }
})
</script>

<style scoped>
.row { display: flex; align-items: center; justify-content: space-between; }
.picker { display: flex; align-items: center; }
.offer-line { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
</style>
