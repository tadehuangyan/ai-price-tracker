<template>
  <div class="page">
    <div class="card">
      <div class="row">
        <h3 class="page-title" style="margin: 0">我的价格追踪</h3>
        <el-button size="small" @click="load">刷新</el-button>
      </div>
      <el-table :data="list" style="margin-top: 12px" v-loading="loading">
        <el-table-column label="商品" min-width="260">
          <template #default="{ row }">
            <div class="prod" @click="router.push(`/product/${row.product_id}`)">
              <img :src="row.image_url || placeholder" />
              <span>{{ row.product_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前价" width="130">
          <template #default="{ row }">
            <b class="price" v-if="row.current_price">￥{{ row.current_price }}</b>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="目标价" width="130">
          <template #default="{ row }">
            <span v-if="row.target_price">￥{{ row.target_price }}</span>
            <span v-else class="muted">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.target_price && row.current_price && row.current_price <= row.target_price" type="success" size="small">已达目标价</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">追踪中</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="添加时间" width="160" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="editTarget(row)">改目标价</el-button>
            <el-popconfirm title="确认取消追踪？" @confirm="remove(row)">
              <template #reference>
                <el-button size="small" type="danger" plain>取消追踪</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !list.length" description="还没有追踪任何商品，去商品页添加吧" />
    </div>

    <div class="card" style="margin-top: 16px">
      <h3 class="page-title" style="margin: 0 0 8px">降价提醒记录</h3>
      <el-table :data="alerts">
        <el-table-column prop="message" label="提醒内容" min-width="300" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_read ? 'info' : 'danger'">{{ row.is_read ? '已读' : '未读' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="targetDialog" title="设置目标价" width="400px">
      <el-input-number v-model="editPrice" :min="0" :precision="2" :step="10" style="width: 200px" />
      <template #footer>
        <el-button @click="targetDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTarget">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'

const router = useRouter()
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20shopping%20bag&image_size=square'

const list = ref<any[]>([])
const alerts = ref<any[]>([])
const loading = ref(false)
const targetDialog = ref(false)
const editPrice = ref<number | undefined>()
const editing = ref<any>(null)

async function load() {
  loading.value = true
  try {
    const [t, a] = await Promise.all([api.get('/api/tracking'), api.get('/api/tracking/alerts')])
    list.value = t.data
    alerts.value = a.data
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}
function editTarget(row: any) {
  editing.value = row
  editPrice.value = row.target_price ?? undefined
  targetDialog.value = true
}
async function saveTarget() {
  try {
    await api.post('/api/tracking', { product_id: editing.value.product_id, target_price: editPrice.value ?? null })
    ElMessage.success('目标价已更新')
    targetDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}
async function remove(row: any) {
  try {
    await api.delete(`/api/tracking/${row.id}`)
    ElMessage.success('已取消追踪')
    load()
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}
onMounted(load)
</script>

<style scoped>
.row { display: flex; align-items: center; justify-content: space-between; }
.prod { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.prod img { width: 40px; height: 40px; object-fit: contain; background: #fafafa; border-radius: 4px; }
.prod span:hover { color: #409eff; }
</style>
