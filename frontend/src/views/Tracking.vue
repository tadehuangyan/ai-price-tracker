<template>
  <div class="page tracking" ref="rootEl">
    <header class="page-head">
      <div class="kicker"><span class="pin-dot"></span>COLLECTION LOG · 采集台账</div>
      <h1 class="page-title" ref="titleEl">价格追踪 · 采集台账</h1>
      <p class="page-sub">凡所留意之物，皆录于册：记其编号、时日与所值几许，待价落之时，钤印为凭。</p>
      <img class="deco deco-flower-head" src="/deco/feather.png" alt="" aria-hidden="true" />
    </header>

    <!-- —— 追踪台账 —— -->
    <section class="board spec-card reveal" data-delay="120">
      <div class="tape board-tape"></div>
      <div class="board-head">
        <div>
          <div class="kicker"><span class="pin-dot"></span>LOT · 追踪台账</div>
          <h2 class="board-title">在录标本</h2>
        </div>
        <div class="board-ops">
          <span class="colophon">ENTRIES · {{ pad(list.length) }}</span>
          <el-button class="mag-btn" size="small" @click="load">刷新</el-button>
        </div>
      </div>

      <!-- 空态：台账空白页 -->
      <div v-if="!loading && !list.length" class="empty-sheet">
        <span class="pin empty-pin" ref="emptyPinEl"></span>
        <img class="deco deco-beetle-empty" src="/deco/mushroom.png" alt="" aria-hidden="true" />
        <div class="empty-frame">
          <p class="annot empty-note">暂无采集记录</p>
          <p class="muted">还没有追踪任何商品，去商品页添加吧</p>
        </div>
      </div>

      <!-- 台账条目 -->
      <div v-else class="ledger" v-loading="loading">
        <article
          v-for="(row, i) in list"
          :key="row.id"
          class="entry reveal"
          :data-delay="Math.min(i * 70, 420)"
        >
          <div class="entry-no">No.{{ pad(i + 1) }}</div>
          <div class="entry-prod" @click="router.push(`/product/${row.product_id}`)">
            <img :src="row.image_url || placeholder" alt="" />
            <div class="prod-info">
              <div class="prod-name">{{ row.product_name }}</div>
              <div class="annot entry-note">采集于 {{ row.created_at }}</div>
            </div>
          </div>
          <div class="entry-nums">
            <div class="num-block">
              <div class="kicker num-label">CURRENT · 当前价</div>
              <b v-if="row.current_price != null" class="big-num"
                ><span
                  class="cnt"
                  :key="`cur-${row.id}-${row.current_price}`"
                  :data-count="parts(row.current_price)[0]"
                  data-prefix="￥"
                ></span
                ><span v-if="parts(row.current_price)[1]" class="dec">{{ parts(row.current_price)[1] }}</span></b
              >
              <span v-else class="muted">--</span>
            </div>
            <div class="num-block">
              <div class="kicker num-label">TARGET · 目标价</div>
              <b v-if="row.target_price != null" class="big-num num-target"
                ><span
                  class="cnt"
                  :key="`tgt-${row.id}-${row.target_price}`"
                  :data-count="parts(row.target_price)[0]"
                  data-prefix="￥"
                ></span
                ><span v-if="parts(row.target_price)[1]" class="dec">{{ parts(row.target_price)[1] }}</span></b
              >
              <span v-else class="muted">未设置</span>
            </div>
          </div>
          <div class="entry-status">
            <span class="seal" :class="statusOf(row).cls">{{ statusOf(row).text }}</span>
            <div class="annot entry-note status-note">{{ statusOf(row).note }}</div>
          </div>
          <div class="entry-ops">
            <el-button class="mag-btn" size="small" @click="editTarget(row)">改目标价</el-button>
            <el-popconfirm title="确认取消追踪？" @confirm="remove(row)">
              <template #reference>
                <el-button class="mag-btn" size="small" type="danger" plain>取消追踪</el-button>
              </template>
            </el-popconfirm>
          </div>
        </article>
      </div>
    </section>

    <!-- —— 提醒摘录 —— -->
    <section class="board spec-card reveal" data-delay="200">
      <div class="board-head">
        <div>
          <div class="kicker"><span class="pin-dot"></span>MEMO · 提醒摘录</div>
          <h2 class="board-title">降价提醒记录</h2>
        </div>
        <span class="colophon">LOGS · {{ pad(alerts.length) }}</span>
      </div>
      <div v-if="alerts.length" class="memo">
        <div
          v-for="(a, i) in alerts"
          :key="a.id ?? i"
          class="memo-row reveal"
          :data-delay="Math.min(i * 50, 300)"
        >
          <span class="memo-no">LOG-{{ pad(i + 1) }}</span>
          <span class="memo-msg">{{ a.message }}</span>
          <span class="memo-time">{{ a.created_at }}</span>
          <span class="seal seal-sm" :class="a.is_read ? 'seal-read' : 'seal-unread'">{{ a.is_read ? '已读' : '未读' }}</span>
        </div>
      </div>
      <p v-else class="annot empty-mini">暂无提醒</p>
    </section>

    <!-- —— 标定价弹窗 —— -->
    <el-dialog v-model="targetDialog" width="420px">
      <template #header>
        <div class="kicker"><span class="pin-dot"></span>TARGET · 标定价</div>
        <div class="dialog-title">设置目标价</div>
      </template>
      <div ref="dialogBody">
        <div class="spec-card dialog-card">
          <div class="tape dialog-tape"></div>
          <p class="annot dialog-note">为《{{ editing?.product_name }}》标定期望之价，待市价落至此线，即刻钤印提醒。</p>
          <div class="kicker dialog-label">TARGET PRICE · 目标价</div>
          <el-input-number v-model="editPrice" :min="0" :precision="2" :step="10" style="width: 200px" />
        </div>
      </div>
      <template #footer>
        <span ref="cancelMag" class="mag"><el-button @click="targetDialog = false">取消</el-button></span>
        <span ref="saveMag" class="mag"><el-button type="primary" @click="saveTarget">保存</el-button></span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import api, { errMsg } from '../api'
import { splitReveal, revealOnScroll, countUp, magnetic, popIn, pinPress, refreshScroll } from '../anim'

const router = useRouter()
const placeholder =
  'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20white%20product%20placeholder%20shopping%20bag&image_size=square'

const rootEl = ref<HTMLDivElement | null>(null)
const titleEl = ref<HTMLHeadingElement | null>(null)
const emptyPinEl = ref<HTMLSpanElement | null>(null)
const dialogBody = ref<HTMLDivElement | null>(null)
const cancelMag = ref<HTMLSpanElement | null>(null)
const saveMag = ref<HTMLSpanElement | null>(null)

const list = ref<any[]>([])
const alerts = ref<any[]>([])
const loading = ref(false)
const targetDialog = ref(false)
const editPrice = ref<number | undefined>()
const editing = ref<any>(null)

// —— 台账排版工具 ——
const pad = (n: number) => String(n).padStart(3, '0')
/** 拆整数/小数：整数交给 countUp，小数静态展示，保证金额不失真 */
function parts(v: unknown): [number, string] {
  const n = Number(v)
  if (!Number.isFinite(n)) return [0, '']
  const int = Math.trunc(n)
  const dec = Math.abs(n - int).toFixed(2).slice(1)
  return [int, dec === '.00' ? '' : dec]
}
function statusOf(row: any) {
  const hit = row.target_price != null && row.current_price != null && row.current_price <= row.target_price
  if (hit) return { text: '已触底', note: '已落至目标价，宜入手', cls: 'seal-hit' }
  if (row.target_price != null) return { text: '等待中', note: '候其价落，静观其变', cls: 'seal-wait' }
  return { text: '降价中', note: '未标目标价，但观涨跌', cls: 'seal-watch' }
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
    await playPage()
    if (!list.value.length) pinPress(emptyPinEl.value)
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

// 弹窗内容入场 + 磁性按钮
watch(targetDialog, async (open) => {
  if (!open) return
  await nextTick()
  popIn(dialogBody.value, 0.06)
  magnet(cancelMag.value)
  magnet(saveMag.value)
})

onMounted(() => {
  splitReveal(titleEl.value, 0.12)
  load()
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

/* —— 台账板 —— */
.board { padding: 22px 26px 26px; }
.board.spec-card:hover { transform: none; box-shadow: var(--shadow-md); }
.board-tape { top: -11px; left: 56px; transform: rotate(-1.6deg); }
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
.board-ops { display: flex; align-items: center; gap: 14px; }
.mag { display: inline-flex; }

/* —— 台账条目 —— */
.ledger { margin-top: 4px; }
.entry {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr) 236px 130px 188px;
  align-items: center;
  gap: 18px;
  padding: 15px 10px;
  transition: background 0.35s ease;
}
.entry + .entry { border-top: 1px dashed var(--line-strong); }
.entry:hover { background: rgba(60, 90, 69, 0.05); }
.entry:hover .entry-note { color: var(--pin); }
.entry-no {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--ink-faint);
}
.entry-prod { display: flex; align-items: center; gap: 12px; min-width: 0; cursor: pointer; }
.entry-prod img {
  width: 46px;
  height: 46px;
  object-fit: contain;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 2px;
  flex: none;
}
.prod-info { min-width: 0; }
.prod-name {
  font-family: var(--serif);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.entry-prod:hover .prod-name { color: var(--green); }
.entry-note { font-size: 12px; margin-top: 3px; transition: color 0.3s; }
.entry-nums { display: flex; gap: 22px; }
.num-block { min-width: 0; }
.num-label { display: block; margin-bottom: 3px; }
.big-num {
  font-family: var(--mono);
  font-size: 21px;
  font-weight: 700;
  color: var(--pin);
  letter-spacing: 0.01em;
  white-space: nowrap;
}
.num-target { color: var(--green); }
.dec { font-size: 13px; }
.entry-status { text-align: center; min-width: 0; }
.status-note { margin-top: 6px; font-size: 11px; line-height: 1.6; }
.entry-ops { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }

/* —— 印章 —— */
.seal {
  font-size: 12px;
  padding: 3px 9px;
  letter-spacing: 0.16em;
  line-height: 1.4;
  white-space: nowrap;
}
.seal-hit {
  color: var(--green);
  border-color: var(--green);
  background: var(--green-soft);
  transform: rotate(-3deg);
}
.seal-wait {
  color: var(--ink-soft);
  border-color: var(--line-strong);
  background: transparent;
  transform: rotate(2deg);
}
.seal-watch {
  color: var(--pin);
  border-color: var(--pin);
  background: var(--pin-soft);
  transform: rotate(-3deg);
}
.seal-sm { font-size: 11px; padding: 2px 7px; transform: rotate(0deg); }
.seal-read { color: var(--ink-faint); border-color: var(--line-strong); background: transparent; }
.seal-unread { color: var(--pin); border-color: var(--pin); background: var(--pin-soft); }

/* —— 空态：台账空白页 —— */
.empty-sheet { position: relative; margin: 12px 0 6px; padding: 30px 20px 26px; }
.empty-pin { top: 16px; left: 50%; margin-left: -5px; }
.empty-frame {
  border: 1px dashed var(--line-strong);
  border-radius: 2px;
  padding: 32px 20px;
  text-align: center;
}
.empty-note {
  font-size: 17px;
  letter-spacing: 0.22em;
  color: var(--ink-soft);
  margin: 0 0 8px;
}

/* —— 提醒摘录 —— */
.memo { margin-top: 4px; }
.memo-row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) 150px 62px;
  gap: 14px;
  align-items: center;
  padding: 11px 10px;
  transition: background 0.35s ease;
}
.memo-row + .memo-row { border-top: 1px dashed var(--line-strong); }
.memo-row:hover { background: rgba(60, 90, 69, 0.05); }
.memo-no {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--ink-faint);
}
.memo-msg {
  font-family: var(--serif);
  font-size: 13.5px;
  color: var(--ink);
  letter-spacing: 0.02em;
  min-width: 0;
}
.memo-time {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
  white-space: nowrap;
}
.empty-mini { margin: 6px 0 2px; }

/* —— 标定价弹窗 —— */
.dialog-title {
  font-family: var(--serif);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin-top: 5px;
  color: var(--ink);
}
.dialog-card { padding: 20px 20px 22px; margin: 6px 0 2px; }
.dialog-tape { top: -10px; right: 28px; transform: rotate(2.2deg); }
.dialog-note { font-size: 13px; line-height: 1.9; margin: 0 0 14px; }
.dialog-label { display: block; margin-bottom: 8px; }

/* —— 透明装饰素材 —— */
.deco { position: absolute; pointer-events: none; z-index: 3; }
.deco-flower-head { width: 100px; top: -16px; right: 6px; opacity: 0.75; transform: rotate(8deg); }
.deco-beetle-empty { width: 90px; top: 14px; left: 50%; margin-left: -230px; opacity: 0.8; transform: rotate(-8deg); }

@media (max-width: 1320px) {
  .entry { grid-template-columns: 56px minmax(0, 1fr) 210px 118px 172px; gap: 12px; }
  .big-num { font-size: 19px; }
}
</style>
