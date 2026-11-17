<template>
  <div class="page">
    <h3 class="page-title">系统管理</h3>
    <el-tabs v-model="tab">
      <!-- 统计概览 -->
      <el-tab-pane label="统计概览" name="stats">
        <div class="stat-grid" v-loading="loadingStats">
          <div class="card stat"><div class="n">{{ stats.product_count ?? '--' }}</div><div class="l">商品数</div></div>
          <div class="card stat"><div class="n">{{ stats.listing_count ?? '--' }}</div><div class="l">在售链接数</div></div>
          <div class="card stat"><div class="n">{{ stats.snapshot_count ?? '--' }}</div><div class="l">价格快照数</div></div>
          <div class="card stat"><div class="n">{{ stats.user_count ?? '--' }}</div><div class="l">注册用户</div></div>
          <div class="card stat"><div class="n">{{ stats.tracking_count ?? '--' }}</div><div class="l">追踪订阅</div></div>
          <div class="card stat"><div class="n">{{ stats.alert_count ?? '--' }}</div><div class="l">降价提醒</div></div>
          <div class="card stat"><div class="n">{{ stats.task_success ?? '--' }}/{{ stats.task_total ?? '--' }}</div><div class="l">采集成功/总任务</div></div>
          <div class="card stat"><div class="n" style="color: #67c23a">{{ stats.success_rate != null ? stats.success_rate + '%' : '--' }}</div><div class="l">近 24h 成功率</div></div>
        </div>
      </el-tab-pane>

      <!-- 数据源 -->
      <el-tab-pane label="数据源管理" name="sources">
        <el-table :data="sources" v-loading="loadingSources">
          <el-table-column prop="platform" label="平台标识" width="140" />
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column label="启用" width="100">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled" @change="(v: any) => toggleSource(row, v)" />
            </template>
          </el-table-column>
          <el-table-column label="采集频率（分钟）" width="180">
            <template #default="{ row }">
              <el-input-number
                :model-value="row.crawl_interval_minutes"
                :min="10"
                size="small"
                @change="(v: any) => saveSource(row, { crawl_interval_minutes: v })"
              />
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="160" />
          <el-table-column label="采集规则配置" min-width="220">
            <template #default="{ row }">
              <el-input
                v-model="row.config"
                size="small"
                type="textarea"
                :rows="1"
                @blur="saveSource(row, {})"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 采集任务 -->
      <el-tab-pane label="采集任务" name="tasks">
        <div class="row" style="margin-bottom: 10px">
          <el-radio-group v-model="taskStatus" size="small" @change="loadTasks(1)">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="success">成功</el-radio-button>
            <el-radio-button label="failed">失败</el-radio-button>
            <el-radio-button label="paused">已暂停</el-radio-button>
          </el-radio-group>
          <el-button size="small" @click="loadTasks(1)">刷新</el-button>
        </div>
        <el-table :data="tasks.items" v-loading="loadingTasks">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column prop="platform" label="平台" width="110" />
          <el-table-column prop="target" label="采集目标" min-width="240" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_run_at" label="最近执行" width="170" />
          <el-table-column label="成功/失败" width="110">
            <template #default="{ row }">{{ row.success_count }} / {{ row.fail_count }}</template>
          </el-table-column>
          <el-table-column prop="last_error" label="错误信息" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="210" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" plain @click="runTask(row)">执行</el-button>
              <el-button
                v-if="row.status !== 'paused'"
                size="small"
                @click="post(`/api/admin/tasks/${row.id}/pause`)"
              >暂停</el-button>
              <el-button
                v-else
                size="small"
                type="success"
                plain
                @click="post(`/api/admin/tasks/${row.id}/resume`)"
              >恢复</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 12px; display: flex; justify-content: center">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="tasks.total"
            :page-size="tasks.page_size"
            :current-page="tasks.page"
            @current-change="loadTasks"
          />
        </div>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <div class="row" style="margin-bottom: 10px">
          <el-input v-model="userKeyword" placeholder="搜索用户名/邮箱" style="width: 260px" clearable @keyup.enter="loadUsers(1)" />
          <el-button type="primary" size="small" @click="loadUsers(1)">搜索</el-button>
        </div>
        <el-table :data="users.items" v-loading="loadingUsers">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="nickname" label="昵称" width="140" />
          <el-table-column prop="email" label="邮箱" min-width="200" />
          <el-table-column label="角色" width="100">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role === 'admin' ? '管理员' : '用户' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
                {{ row.status === 'active' ? '正常' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button
                size="small"
                :type="row.status === 'active' ? 'danger' : 'success'"
                plain
                @click="toggleUser(row)"
              >{{ row.status === 'active' ? '禁用' : '启用' }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 12px; display: flex; justify-content: center">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="users.total"
            :page-size="users.page_size"
            :current-page="users.page"
            @current-change="loadUsers"
          />
        </div>
      </el-tab-pane>

      <!-- 敏感词管理 -->
      <el-tab-pane label="敏感词管理" name="words">
        <div class="row" style="margin-bottom: 10px">
          <div class="row" style="gap: 8px">
            <el-input
              v-model="wordKeyword"
              placeholder="搜索敏感词"
              style="width: 220px"
              clearable
              @keyup.enter="loadWords(1)"
            />
            <el-button type="primary" size="small" @click="loadWords(1)">搜索</el-button>
          </div>
          <div class="row" style="gap: 8px">
            <el-button type="primary" size="small" @click="openWordDialog">新增敏感词</el-button>
            <el-button size="small" @click="openBatchDialog">批量导入</el-button>
          </div>
        </div>
        <el-table :data="words.items" v-loading="loadingWords">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column prop="word" label="敏感词" width="220" />
          <el-table-column prop="category" label="分类" width="140" />
          <el-table-column prop="created_at" label="创建时间" min-width="160" />
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button size="small" type="danger" plain @click="removeWord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 12px; display: flex; justify-content: center">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="words.total"
            :page-size="words.page_size"
            :current-page="words.page"
            @current-change="loadWords"
          />
        </div>

        <!-- 新增敏感词 -->
        <el-dialog v-model="wordDialog" title="新增敏感词" width="420px">
          <el-form label-width="70px">
            <el-form-item label="敏感词">
              <el-input v-model="newWord.word" placeholder="输入敏感词" />
            </el-form-item>
            <el-form-item label="分类">
              <el-input v-model="newWord.category" placeholder="如：违法 / 违禁品 / 通用" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="wordDialog = false">取消</el-button>
            <el-button type="primary" @click="addWord">确定</el-button>
          </template>
        </el-dialog>

        <!-- 批量导入 -->
        <el-dialog v-model="batchDialog" title="批量导入敏感词" width="460px">
          <el-input v-model="batchText" type="textarea" :rows="8" placeholder="每行一个词" />
          <el-input v-model="batchCategory" placeholder="分类（选填，默认：通用）" style="margin-top: 10px" />
          <template #footer>
            <el-button @click="batchDialog = false">取消</el-button>
            <el-button type="primary" :loading="importing" @click="batchImport">导入</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- 日志 -->
      <el-tab-pane label="系统日志" name="logs">
        <div class="row" style="margin-bottom: 10px">
          <el-radio-group v-model="logLevel" size="small" @change="loadLogs(1)">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="INFO">INFO</el-radio-button>
            <el-radio-button label="ERROR">ERROR</el-radio-button>
          </el-radio-group>
          <el-button size="small" @click="loadLogs(1)">刷新</el-button>
        </div>
        <el-table :data="logs.items" v-loading="loadingLogs">
          <el-table-column prop="id" label="#" width="80" />
          <el-table-column label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="row.level === 'ERROR' ? 'danger' : 'info'" size="small">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="module" label="模块" width="120" />
          <el-table-column prop="message" label="内容" min-width="380" show-overflow-tooltip />
          <el-table-column prop="created_at" label="时间" width="170" />
        </el-table>
        <div style="margin-top: 12px; display: flex; justify-content: center">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="logs.total"
            :page-size="logs.page_size"
            :current-page="logs.page"
            @current-change="loadLogs"
          />
        </div>
      </el-tab-pane>

      <!-- 配置 -->
      <el-tab-pane label="系统配置" name="config">
        <el-table :data="configs" v-loading="loadingConfig">
          <el-table-column prop="key" label="配置项" width="240" />
          <el-table-column prop="description" label="说明" min-width="220" />
          <el-table-column label="值" min-width="260">
            <template #default="{ row }">
              <el-input v-model="row.value" size="small" />
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="170" />
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="saveConfig(row)">保存</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'

const tab = ref('stats')

// ---- 统计 ----
const stats = ref<any>({})
const loadingStats = ref(false)
async function loadStats() {
  loadingStats.value = true
  try {
    const { data } = await api.get('/api/admin/stats')
    stats.value = data
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loadingStats.value = false
  }
}

// ---- 数据源 ----
const sources = ref<any[]>([])
const loadingSources = ref(false)
async function loadSources() {
  loadingSources.value = true
  const { data } = await api.get('/api/admin/datasources')
  sources.value = data
  loadingSources.value = false
}
async function toggleSource(row: any, v: boolean) {
  await saveSource(row, { enabled: v })
}
async function saveSource(row: any, patch: any) {
  try {
    await api.post('/api/admin/datasources', {
      platform: row.platform,
      name: row.name,
      enabled: patch.enabled ?? row.enabled,
      crawl_interval_minutes: patch.crawl_interval_minutes ?? row.crawl_interval_minutes,
      config: patch.config ?? row.config,
    })
    row.enabled = patch.enabled ?? row.enabled
    if (patch.crawl_interval_minutes) row.crawl_interval_minutes = patch.crawl_interval_minutes
    ElMessage.success('数据源已保存')
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

// ---- 任务 ----
const tasks = ref<any>({ items: [], total: 0, page: 1, page_size: 20 })
const taskStatus = ref('')
const loadingTasks = ref(false)
async function loadTasks(page = 1) {
  loadingTasks.value = true
  try {
    const { data } = await api.get('/api/admin/tasks', { params: { page, status: taskStatus.value } })
    tasks.value = data
  } finally {
    loadingTasks.value = false
  }
}
async function runTask(row: any) {
  try {
    const { data } = await api.post(`/api/admin/tasks/${row.id}/run`)
    if (data.ok) ElMessage.success('采集成功')
    else ElMessage.error('采集失败：' + data.error)
    loadTasks(tasks.value.page)
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}
async function post(url: string) {
  try {
    await api.post(url)
    ElMessage.success('操作成功')
    loadTasks(tasks.value.page)
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}
const statusType = (s: string) =>
  ({ success: 'success', failed: 'danger', running: 'primary', paused: 'warning' } as any)[s] || 'info'
const statusText = (s: string) =>
  ({ success: '成功', failed: '失败', running: '执行中', paused: '已暂停', pending: '待执行' } as any)[s] || s

// ---- 用户 ----
const users = ref<any>({ items: [], total: 0, page: 1, page_size: 20 })
const userKeyword = ref('')
const loadingUsers = ref(false)
async function loadUsers(page = 1) {
  loadingUsers.value = true
  try {
    const { data } = await api.get('/api/admin/users', { params: { page, keyword: userKeyword.value } })
    users.value = data
  } finally {
    loadingUsers.value = false
  }
}
async function toggleUser(row: any) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  try {
    await api.post(`/api/admin/users/${row.id}/status?status=${next}`)
    row.status = next
    ElMessage.success('操作成功')
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

// ---- 敏感词 ----
const words = ref<any>({ items: [], total: 0, page: 1, page_size: 20 })
const wordKeyword = ref('')
const loadingWords = ref(false)
const wordDialog = ref(false)
const newWord = ref({ word: '', category: '' })
const batchDialog = ref(false)
const batchText = ref('')
const batchCategory = ref('')
const importing = ref(false)

async function loadWords(page = 1) {
  loadingWords.value = true
  try {
    const { data } = await api.get('/api/admin/sensitive-words', {
      params: { page, keyword: wordKeyword.value },
    })
    words.value = data
  } finally {
    loadingWords.value = false
  }
}
function openWordDialog() {
  newWord.value = { word: '', category: '' }
  wordDialog.value = true
}
function openBatchDialog() {
  batchText.value = ''
  batchCategory.value = ''
  batchDialog.value = true
}
async function addWord() {
  const word = newWord.value.word.trim()
  if (!word) {
    ElMessage.warning('请输入敏感词')
    return
  }
  try {
    await api.post('/api/admin/sensitive-words', {
      word,
      category: newWord.value.category.trim() || '通用',
    })
    ElMessage.success('已添加')
    wordDialog.value = false
    loadWords(1)
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}
async function batchImport() {
  const text = batchText.value.trim()
  if (!text) {
    ElMessage.warning('请输入要导入的词')
    return
  }
  importing.value = true
  try {
    const { data } = await api.post('/api/admin/sensitive-words/batch', {
      words: text,
      category: batchCategory.value.trim() || '通用',
    })
    ElMessage.success(`导入完成：新增 ${data.added} 个，跳过 ${data.skipped} 个`)
    batchDialog.value = false
    loadWords(1)
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    importing.value = false
  }
}
async function removeWord(row: any) {
  try {
    await api.delete(`/api/admin/sensitive-words/${row.id}`)
    ElMessage.success('已删除')
    loadWords(words.value.page)
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

// ---- 日志 ----
const logs = ref<any>({ items: [], total: 0, page: 1, page_size: 30 })
const logLevel = ref('')
const loadingLogs = ref(false)
async function loadLogs(page = 1) {
  loadingLogs.value = true
  try {
    const { data } = await api.get('/api/admin/logs', { params: { page, level: logLevel.value } })
    logs.value = data
  } finally {
    loadingLogs.value = false
  }
}

// ---- 配置 ----
const configs = ref<any[]>([])
const loadingConfig = ref(false)
async function loadConfig() {
  loadingConfig.value = true
  const { data } = await api.get('/api/admin/config')
  configs.value = data
  loadingConfig.value = false
}
async function saveConfig(row: any) {
  try {
    await api.put('/api/admin/config', { key: row.key, value: row.value })
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(errMsg(e))
  }
}

onMounted(() => {
  loadStats()
  loadSources()
  loadTasks(1)
  loadUsers(1)
  loadLogs(1)
  loadConfig()
  loadWords(1)
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat { text-align: center; padding: 22px 10px; }
.stat .n { font-size: 26px; font-weight: 800; color: #409eff; }
.stat .l { margin-top: 6px; color: #909399; font-size: 13px; }
.row { display: flex; align-items: center; justify-content: space-between; }
</style>
