<template>
  <div class="page" v-loading="loading">
    <template v-if="product">
      <div class="card head">
        <img class="cover" :src="product.image_url || placeholder" alt="" />
        <div class="info">
          <h2 style="margin: 0 0 8px">{{ product.name }}</h2>
          <div class="muted">{{ product.category }} · {{ product.brand || '未知品牌' }}</div>
          <div class="price" style="font-size: 26px; margin-top: 10px">
            ￥{{ product.min_price ?? '--' }}
            <span class="muted" style="font-size: 13px">全平台最低价</span>
          </div>
          <div style="margin-top: 14px; display: flex; gap: 10px; align-items: center">
            <el-button type="primary" @click="trackDialog = true">
              <el-icon style="margin-right: 4px"><Timer /></el-icon>加入价格追踪
            </el-button>
            <el-button @click="router.push(`/compare?ids=${product.id}`)">多平台比价</el-button>
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
                <el-icon color="#67c23a"><MagicStick /></el-icon>
              </template>
            </el-input>
            <el-button type="success" @click="goAdvisor">
              问 AI 导购
              <el-icon style="margin-left: 4px"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top: 16px">
        <div class="row">
          <span class="block-title">平台报价</span>
          <el-radio-group v-model="days" size="small" @change="loadTrend">
            <el-radio-button :label="30">近 30 天</el-radio-button>
            <el-radio-button :label="90">近 90 天</el-radio-button>
            <el-radio-button :label="180">近 180 天</el-radio-button>
            <el-radio-button :label="365">近一年</el-radio-button>
          </el-radio-group>
        </div>
        <el-table :data="product.listings" style="margin-top: 10px">
          <el-table-column prop="platform" label="平台" width="130">
            <template #default="{ row }">
              <el-tag size="small">{{ platformName(row.platform) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="商品" min-width="220" show-overflow-tooltip />
          <el-table-column label="当前价" width="130">
            <template #default="{ row }"><b class="price">￥{{ row.current_price }}</b></template>
          </el-table-column>
          <el-table-column label="最近采集" width="170">
            <template #default="{ row }"><span class="muted">{{ row.last_crawled_at || '未采集' }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-link v-if="row.url" :href="row.url" target="_blank" type="primary">前往购买</el-link>
            </template>
          </el-table-column>
        </el-table>

        <div class="stats" v-if="trend">
          <div class="stat"><div class="label">当前价</div><div class="value price">￥{{ trend.current_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">{{ days }} 天最低</div><div class="value" style="color: #67c23a">￥{{ trend.min_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">{{ days }} 天最高</div><div class="value" style="color: #e6a23c">￥{{ trend.max_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">平均价</div><div class="value">￥{{ trend.avg_price ?? '--' }}</div></div>
          <div class="stat"><div class="label">数据点</div><div class="value">{{ trend.points.length }} 天</div></div>
        </div>
        <PriceTrendChart :points="trend?.points || []" :title="`历史价格走势（近 ${days} 天）`" style="margin-top: 8px" />
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
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import PriceTrendChart from '../components/PriceTrendChart.vue'

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

onMounted(load)
</script>

<style scoped>
.head { display: flex; gap: 20px; }
.cover { width: 220px; height: 220px; object-fit: contain; background: #fafafa; border-radius: 8px; }
.info { flex: 1; }
.ask-bar { display: flex; gap: 10px; margin-top: 12px; max-width: 520px; }
.ask-bar .el-input { flex: 1; }
.row { display: flex; align-items: center; justify-content: space-between; }
.block-title { font-size: 15px; font-weight: 600; }
.stats { display: flex; gap: 24px; margin: 16px 0 4px; flex-wrap: wrap; }
.stat .label { font-size: 12px; color: #909399; }
.stat .value { font-size: 18px; font-weight: 700; margin-top: 4px; }
</style>
