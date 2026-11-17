<template>
  <div class="page" ref="pageEl">
    <div class="page-head">
      <div class="kicker reveal" data-delay="0"><span class="pin-dot"></span>ARCHIVE ADMIN · 馆务</div>
      <h2 class="page-title" ref="titleEl">系统管理</h2>
      <div class="page-sub reveal" data-delay="90">标本的采集、登记与剔除 · 皆由馆务执掌</div>
      <span class="seal head-seal">馆务钤记</span>
      <img src="/deco/quill-ink.png" alt="" aria-hidden="true" class="deco deco-quill" />
      <img src="/deco/beetle.png" alt="" aria-hidden="true" class="deco deco-beetle" />
    </div>
    <el-tabs v-model="tab" class="admin-tabs">
      <!-- 统计概览 -->
      <el-tab-pane label="统计概览" name="stats">
        <div class="card spec-card group-card reveal" data-delay="60">
          <div class="kicker group-kicker"><span class="pin-dot"></span>01 · STAT LEDGER · 统计台账</div>
          <div class="stat-grid" v-loading="loadingStats">
            <div class="stat reveal" data-delay="60">
              <div class="n"><span :data-count="stats.product_count">{{ stats.product_count ?? '--' }}</span></div>
              <div class="l"><span class="en">PRODUCTS</span>商品数</div>
            </div>
            <div class="stat reveal" data-delay="120">
              <div class="n"><span :data-count="stats.listing_count">{{ stats.listing_count ?? '--' }}</span></div>
              <div class="l"><span class="en">LISTINGS</span>在售链接数</div>
            </div>
            <div class="stat reveal" data-delay="180">
              <div class="n"><span :data-count="stats.snapshot_count">{{ stats.snapshot_count ?? '--' }}</span></div>
              <div class="l"><span class="en">SNAPSHOTS</span>价格快照数</div>
            </div>
            <div class="stat reveal" data-delay="240">
              <div class="n"><span :data-count="stats.user_count">{{ stats.user_count ?? '--' }}</span></div>
              <div class="l"><span class="en">MEMBERS</span>注册用户</div>
            </div>
            <div class="stat reveal" data-delay="300">
              <div class="n"><span :data-count="stats.tracking_count">{{ stats.tracking_count ?? '--' }}</span></div>
              <div class="l"><span class="en">TRACKINGS</span>追踪订阅</div>
            </div>
            <div class="stat reveal" data-delay="360">
              <div class="n"><span :data-count="stats.alert_count">{{ stats.alert_count ?? '--' }}</span></div>
              <div class="l"><span class="en">ALERTS</span>降价提醒</div>
            </div>
            <div class="stat reveal" data-delay="420">
              <div class="n">
                <span :data-count="stats.task_success">{{ stats.task_success ?? '--' }}</span><i class="sep">/</i><span :data-count="stats.task_total">{{ stats.task_total ?? '--' }}</span>
              </div>
              <div class="l"><span class="en">TASKS</span>采集成功/总任务</div>
            </div>
            <div class="stat reveal" data-delay="480">
              <div class="n good">
                <span :data-count="stats.success_rate" data-suffix="%">{{ stats.success_rate != null ? stats.success_rate + '%' : '--' }}</span>
              </div>
              <div class="l"><span class="en">UPTIME</span>近 24h 成功率</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 数据源 -->
      <el-tab-pane label="数据源管理" name="sources">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>02 · DATA SOURCES · 数据源</div>
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
        </div>
      </el-tab-pane>

      <!-- 采集任务 -->
      <el-tab-pane label="采集任务" name="tasks">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>03 · CRAWL TASKS · 采集任务</div>
          <div class="row" style="margin-bottom: 10px">
            <el-radio-group v-model="taskStatus" size="small" @change="loadTasks(1)">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="success">成功</el-radio-button>
              <el-radio-button label="failed">失败</el-radio-button>
              <el-radio-button label="paused">已暂停</el-radio-button>
            </el-radio-group>
            <el-button size="small" class="mag-btn" @click="loadTasks(1)">刷新</el-button>
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
        </div>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>04 · MEMBERS · 用户管理</div>
          <div class="row" style="margin-bottom: 10px">
            <el-input v-model="userKeyword" placeholder="搜索用户名/邮箱" style="width: 260px" clearable @keyup.enter="loadUsers(1)" />
            <el-button type="primary" size="small" class="mag-btn" @click="loadUsers(1)">搜索</el-button>
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
        </div>
      </el-tab-pane>

      <!-- 敏感词管理 -->
      <el-tab-pane label="敏感词管理" name="words">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>05 · STOP LIST · 敏感词剔除</div>
          <div class="row" style="margin-bottom: 10px">
            <div class="row" style="gap: 8px">
              <el-input
                v-model="wordKeyword"
                placeholder="搜索敏感词"
                style="width: 220px"
                clearable
                @keyup.enter="loadWords(1)"
              />
              <el-button type="primary" size="small" class="mag-btn" @click="loadWords(1)">搜索</el-button>
            </div>
            <div class="row" style="gap: 8px">
              <el-button type="primary" size="small" class="mag-btn" @click="openWordDialog">新增敏感词</el-button>
              <el-button size="small" class="mag-btn" @click="openBatchDialog">批量导入</el-button>
            </div>
          </div>
          <el-table :data="words.items" v-loading="loadingWords">
            <el-table-column prop="id" label="#" width="70" />
            <el-table-column prop="word" label="敏感词" width="220">
              <template #default="{ row }">
                <span class="word-chip"><i class="pin word-pin"></i>{{ row.word }}</span>
              </template>
            </el-table-column>
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
        </div>
      </el-tab-pane>

      <!-- 日志 -->
      <el-tab-pane label="系统日志" name="logs">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>06 · JOURNAL · 系统日志</div>
          <div class="row" style="margin-bottom: 10px">
            <el-radio-group v-model="logLevel" size="small" @change="loadLogs(1)">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="INFO">INFO</el-radio-button>
              <el-radio-button label="ERROR">ERROR</el-radio-button>
            </el-radio-group>
            <el-button size="small" class="mag-btn" @click="loadLogs(1)">刷新</el-button>
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
        </div>
      </el-tab-pane>

      <!-- 模拟邮件记录 -->
      <el-tab-pane label="邮件记录" name="mails">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>07 · POST ROOM · 邮件记录</div>
          <div class="row" style="margin-bottom: 10px">
            <el-radio-group v-model="mailCategory" size="small" @change="loadMails(1)">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="verify_code">验证码</el-radio-button>
              <el-radio-button label="price_alert">降价提醒</el-radio-button>
              <el-radio-button label="subscribe">订阅确认</el-radio-button>
              <el-radio-button label="system">系统通知</el-radio-button>
            </el-radio-group>
            <el-input v-model="mailKeyword" size="small" placeholder="收件人 / 主题" style="width: 200px" clearable @keyup.enter="loadMails(1)" />
            <el-button size="small" class="mag-btn" @click="loadMails(1)">查询</el-button>
          </div>
          <div class="muted" style="margin-bottom: 10px">
            模拟邮箱（沙箱邮件）：SMTP 端口受限，系统邮件不真实外发，仅在此记录"模拟投递"结果（类比支付宝沙箱）。
          </div>
          <el-table :data="mails.items" v-loading="loadingMails">
            <el-table-column prop="id" label="#" width="70" />
            <el-table-column prop="to_email" label="收件人" width="190" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.category === 'verify_code' ? 'warning' : row.category === 'price_alert' ? 'danger' : row.category === 'subscribe' ? 'success' : 'info'">{{ row.category_name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
            <el-table-column label="验证码" width="90">
              <template #default="{ row }">{{ row.code || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default>
                <el-tag size="small" type="success">模拟投递</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="查看" width="90">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="viewMail(row)">详情</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="170" />
          </el-table>
          <div style="margin-top: 12px; display: flex; justify-content: center">
            <el-pagination
              background
              layout="total, prev, pager, next"
              :total="mails.total"
              :page-size="mails.page_size"
              :current-page="mails.page"
              @current-change="loadMails"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- 配置 -->
      <el-tab-pane label="系统配置" name="config">
        <div class="card spec-card group-card">
          <div class="kicker group-kicker"><span class="pin-dot"></span>08 · SETTINGS · 系统配置</div>
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
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="mailDetailVisible" :title="mailDetail?.subject || '邮件详情'" width="560px">
      <div class="muted" style="margin-bottom: 8px">
        收件人：{{ mailDetail?.to_email }} · 时间：{{ mailDetail?.created_at }} · 状态：模拟投递（sent）
      </div>
      <div style="white-space: pre-wrap; line-height: 1.8">{{ mailDetail?.body }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { countUp, magnetic, refreshScroll, revealOnScroll, splitReveal } from '../anim'

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

// ---- 模拟邮件记录 ----
const mails = ref<any>({ items: [], total: 0, page: 1, page_size: 20 })
const mailCategory = ref('')
const mailKeyword = ref('')
const loadingMails = ref(false)
const mailDetailVisible = ref(false)
const mailDetail = ref<any>(null)
async function loadMails(page = 1) {
  loadingMails.value = true
  try {
    const { data } = await api.get('/api/mail/admin/list', {
      params: { page, category: mailCategory.value, keyword: mailKeyword.value },
    })
    mails.value = data
  } finally {
    loadingMails.value = false
  }
}
function viewMail(row: any) {
  mailDetail.value = row
  mailDetailVisible.value = true
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
  loadMails(1)
  loadConfig()
  loadWords(1)
})

// ================= 标本手记 · 动效（纯表现层，不改动上方业务逻辑） =================
const pageEl = ref<HTMLElement>()
const titleEl = ref<HTMLElement>()

function runCounts() {
  pageEl.value?.querySelectorAll<HTMLElement>('[data-count]').forEach((el) => countUp(el))
}

// 异步数据到位后：关键数字滚动 + 刷新滚动触发器
watch([stats, sources, tasks, users, words, logs, mails, configs], () => {
  nextTick(() => {
    runCounts()
    refreshScroll()
  })
})

// 切换管理区后刷新滚动测量
watch(tab, () => nextTick(() => refreshScroll()))

onMounted(() => {
  splitReveal(titleEl.value ?? null, 0.12)
  revealOnScroll(pageEl.value)
  pageEl.value?.querySelectorAll<HTMLElement>('.mag-btn').forEach((el) => magnetic(el))
})
</script>

<style scoped>
.page-head { position: relative; margin-bottom: 16px; }
.head-seal {
  position: absolute; right: 106px; top: 8px;
  font-size: 13px; padding: 4px 11px;
}

/* —— 透明装饰素材（标本点缀，纯表现层） —— */
.deco { position: absolute; pointer-events: none; user-select: none; z-index: 2; }
.deco-quill {
  width: 90px; right: 2px; top: -18px;
  transform: rotate(-5deg); opacity: 0.75;
}
.deco-beetle {
  width: 70px; left: 4px; top: -22px;
  transform: rotate(8deg); opacity: 0.7;
}

/* —— 管理区分组纸卡 —— */
.group-card { padding: 18px 22px 22px; }
.group-card:hover { transform: none; box-shadow: var(--shadow-md); }
.group-kicker { display: block; margin-bottom: 14px; }

/* —— 统计台账 —— */
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.stat {
  text-align: center; padding: 18px 10px;
  background: var(--paper-3); border: 1px dashed var(--line-strong); border-radius: 2px;
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.35s;
}
.stat:hover { transform: translateY(-3px); box-shadow: var(--shadow-sm); }
.stat .n {
  font-family: var(--mono); font-size: 24px; font-weight: 700;
  color: var(--green); letter-spacing: 0.02em;
}
.stat .n .sep { font-style: normal; color: var(--ink-faint); font-weight: 400; margin: 0 2px; }
.stat .n.good { color: var(--green); }
.stat .l {
  margin-top: 6px; color: var(--ink-faint); font-size: 12px; letter-spacing: 0.1em;
}
.stat .l .en {
  display: block; font-family: var(--mono); font-size: 9px;
  letter-spacing: 0.2em; margin-bottom: 3px; color: var(--ink-faint);
}

/* —— 工具行 —— */
.row { display: flex; align-items: center; justify-content: space-between; }

/* —— 敏感词：剔除标签（红点标记） —— */
.word-chip {
  display: inline-flex; align-items: center;
  padding: 3px 11px 3px 9px; border-radius: 2px;
  border: 1px dashed var(--pin); background: var(--pin-soft);
  font-family: var(--kai); font-size: 13px; letter-spacing: 0.05em; color: var(--ink);
}
.word-pin {
  position: static; display: inline-block;
  margin-right: 7px; vertical-align: 1px;
}

/* —— 标签页 —— */
.admin-tabs :deep(.el-tabs__item) { font-family: var(--serif); letter-spacing: 0.08em; }
</style>
