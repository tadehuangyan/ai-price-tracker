<template>
  <div class="advice-card">
    <div class="advice-head">
      <span class="kicker"><span class="pin-dot"></span>ADVICE · 购买建议</span>
      <span :class="['stamp', card.action]">{{ actionLabel }}</span>
    </div>
    <div v-if="card.summary" class="advice-summary">{{ card.summary }}</div>
    <div class="conf-row">
      <span class="conf-label">置信度</span>
      <div class="conf-bar"><i :style="{ width: confPct + '%' }"></i></div>
      <span class="conf-num">{{ confPct }}%</span>
    </div>
    <ul v-if="card.evidence?.length" class="evidence">
      <li v-for="(e, i) in card.evidence" :key="i">{{ e }}</li>
    </ul>
    <div class="advice-foot">依据系统收录的价格数据结构化生成 · 仅供参考</div>
  </div>
</template>

<script setup lang="ts">
/**
 * 购买建议卡组件：展示 AI 结构化输出的购买建议——"印章"式动作徽章（值得购买/建议等待/继续观望）、
 * 结论摘要、置信度进度条与支撑依据列表。无 emit，纯展示组件。
 */
import { computed } from 'vue'

// 购买建议卡数据结构（AI 结构化输出）
export interface AdviceCardData {
  action: 'buy' | 'wait' | 'watch'
  confidence: number
  summary: string
  evidence: string[]
}

// card：购买建议卡数据（购买动作、置信度 0~1、结论摘要、依据列表），由父组件传入
const props = defineProps<{ card: AdviceCardData }>()

// 购买动作 → 中文印章文案
const ACTION_LABELS: Record<string, string> = {
  buy: '值得购买',
  wait: '建议等待',
  watch: '继续观望',
}
// 印章文案（未知动作兜底为"继续观望"）
const actionLabel = computed(() => ACTION_LABELS[props.card.action] || '继续观望')
// 置信度 0~1 转百分比整数，供进度条宽度与数字展示使用
const confPct = computed(() => Math.round((props.card.confidence || 0) * 100))
</script>

<style scoped>
/* 建议卡整体：纸感卡片 + 左侧墨绿标线 + 旋转印章徽章 + 置信度进度条 + 依据圆点列表 */
.advice-card {
  position: relative;
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  background: var(--paper-2);
  border-radius: 2px;
  padding: 10px 13px 9px;
  margin-bottom: 8px;
  min-width: 240px;
  max-width: 360px;
}
.advice-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-bottom: 6px;
}
.stamp {
  font-family: var(--serif); font-size: 12px; font-weight: 700; letter-spacing: 0.12em;
  padding: 3px 10px; border-radius: 2px; transform: rotate(-2deg); white-space: nowrap;
  border: 1.5px solid currentColor;
}
.stamp.buy { color: var(--green); background: var(--green-soft); }
.stamp.wait { color: var(--pin); background: var(--pin-soft); }
.stamp.watch { color: var(--sage); background: var(--paper-3); }
.advice-summary {
  font-family: var(--kai); font-size: 14px; line-height: 1.7;
  color: var(--ink); letter-spacing: 0.03em; margin-bottom: 8px;
}
.conf-row { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
.conf-label {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em;
  color: var(--ink-faint); white-space: nowrap;
}
.conf-bar {
  flex: 1; height: 5px; background: var(--paper-3);
  border: 1px solid var(--line); border-radius: 2px; overflow: hidden;
}
.conf-bar i {
  display: block; height: 100%; background: var(--green); opacity: 0.75;
  transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.conf-num {
  font-family: var(--mono); font-size: 12px; color: var(--ink-soft);
  min-width: 34px; text-align: right;
}
.evidence {
  margin: 0 0 6px; padding: 0; list-style: none;
}
.evidence li {
  position: relative; padding-left: 13px;
  font-family: var(--kai); font-size: 13px; line-height: 1.75;
  color: var(--ink-soft); letter-spacing: 0.02em;
}
.evidence li::before {
  content: ""; position: absolute; left: 1px; top: 9px;
  width: 5px; height: 5px; border-radius: 50%; background: var(--pin);
}
.advice-foot {
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.12em;
  color: var(--ink-faint); margin-top: 4px;
}
</style>
