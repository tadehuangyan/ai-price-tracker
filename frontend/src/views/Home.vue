<template>
  <div class="page">
    <div class="card search-card">
      <div class="search-row">
        <el-input
          v-model="keyword"
          size="large"
          placeholder="输入商品关键词搜索，或粘贴商品链接即时采集，如：iPhone / https://item.jd.com/xxx.html"
          clearable
          @keyup.enter="onSubmit"
        >
          <template #append>
            <el-button size="large" type="primary" :loading="realtimeLoading" @click="onSubmit">
              <el-icon v-if="!isUrlInput" style="margin-right: 4px"><Search /></el-icon>
              {{ isUrlInput ? '即时采集' : '搜索' }}
            </el-button>
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
      <div class="filters">
        <el-radio-group v-model="category" size="small" @change="search(1)">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button v-for="c in categories" :key="c.category" :label="c.category">
            {{ c.category }}（{{ c.count }}）
          </el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="sort" size="small" @change="search(1)" style="margin-left: auto">
          <el-radio-button label="random">随机</el-radio-button>
          <el-radio-button label="price_asc">价格从低到高</el-radio-button>
          <el-radio-button label="price_desc">价格从高到低</el-radio-button>
          <el-radio-button label="newest">最新上架</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 全网新发现：数据库之外的实时商品 -->
    <div class="card discover-card" v-if="discoverItems.length || discoverLoading">
      <div class="discover-head">
        <span class="block-title">全网新发现</span>
        <el-button size="small" :loading="discoverLoading" @click="loadDiscover(1)">
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
        </div>
      </div>
    </div>

    <div v-loading="loading" class="grid">
      <div v-for="p in items" :key="p.id" class="item card" @click="router.push(`/product/${p.id}`)">
        <div class="img-wrap">
          <img :src="p.image_url || placeholder" alt="" />
        </div>
        <div class="name" :title="p.name">{{ p.name }}</div>
        <div class="meta">
          <span class="price" v-if="p.min_price">￥{{ p.min_price }}</span>
          <span class="muted" v-else>暂无价格</span>
        </div>
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'

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

// ---- 全网新发现 ----
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
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    realtimeLoading.value = false
  }
}

onMounted(() => {
  search(1)
  loadCategories()
  loadDiscover()
})
</script>

<style scoped>
.search-card { margin-bottom: 16px; }
.filters { display: flex; align-items: center; margin-top: 12px; gap: 12px; flex-wrap: wrap; }
.realtime-result { margin-top: 10px; }
.discover-card { margin-bottom: 16px; }
.discover-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.block-title { font-size: 15px; font-weight: 600; }
.discover-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 14px; min-height: 120px;
}
.discover-item {
  cursor: pointer; border: 1px solid #ebeef5; border-radius: 8px; padding: 10px;
  transition: transform .18s, box-shadow .18s, border-color .18s;
}
.discover-item:hover { transform: translateY(-3px); box-shadow: 0 6px 16px rgba(0,0,0,.08); border-color: #e6a23c; }
.d-img { position: relative; height: 130px; background: #fafafa; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.d-img img { max-width: 100%; max-height: 100%; object-fit: contain; }
.d-badge { position: absolute; top: 6px; left: 6px; }
.d-name { margin: 8px 0 6px; font-size: 13px; line-height: 1.4; height: 37px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.d-meta { display: flex; align-items: center; justify-content: space-between; }
.grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 16px; min-height: 200px;
}
.item { cursor: pointer; transition: transform .18s, box-shadow .18s; padding: 12px; }
.item:hover { transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,0,0,.1); }
.img-wrap { height: 160px; display: flex; align-items: center; justify-content: center; background: #fafafa; border-radius: 6px; overflow: hidden; }
.img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
.name { margin: 10px 0 6px; font-size: 14px; line-height: 1.4; height: 40px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.meta { display: flex; align-items: center; justify-content: space-between; }
.pager { display: flex; justify-content: center; margin-top: 18px; }
</style>
