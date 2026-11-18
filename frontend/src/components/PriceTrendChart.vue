<template>
  <div ref="el" :style="{ height: height + 'px', width: '100%' }"></div>
</template>

<script setup lang="ts">
/**
 * 历史价格走势图组件：基于 ECharts 渲染单商品历史价格曲线（标注最高价/最低价/当前价），
 * 传入 compareSeries 时切换为多商品对比曲线，配色沿用全站"标本手记"视觉风格。
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

// points：单商品价格点序列；compareSeries：多商品对比序列（非空则进入对比模式）；height/title：图表高度与标题
const props = withDefaults(
  defineProps<{
    points: { date: string; price: number; platform?: string }[]
    height?: number
    title?: string
    compareSeries?: { name: string; data: { date: string; price: number }[] }[]
  }>(),
  { height: 300, title: '历史价格走势', compareSeries: () => [] }
)

// —— 标本手记色板（与 style.css 保持一致） ——
const C = {
  ink: '#26231c',
  inkSoft: '#5c5546',
  inkFaint: '#8d8574',
  line: '#d9d0bc',
  lineStrong: '#b9aa8e',
  green: '#3c5a45',
  pin: '#b0603c',
  sage: '#93a596',
  paper2: '#fbf8ef',
}
const MONO = '"JetBrains Mono", "SFMono-Regular", Consolas, monospace'
// 对比线序列配色：墨绿 / 朱砂 / 墨 / 苔绿，绝不用默认蓝
const PALETTE = ['#3c5a45', '#b0603c', '#26231c', '#93a596', '#8d8574', '#5d7a66']

// 图表容器 DOM 与 ECharts 实例
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

/**
 * 构建并应用 ECharts 配置：对比模式下把各商品序列按日期对齐后绘制多条平滑曲线；
 * 单商品模式下绘制价格走势，并标注最高价、最低价与当前价参考线。
 */
function render() {
  if (!chart) return
  const useCompare = props.compareSeries.length > 0
  let series: any[]
  let categories: string[]

  if (useCompare) {
    const dateSet = new Set<string>()
    props.compareSeries.forEach((s) => s.data.forEach((d) => dateSet.add(d.date)))
    categories = [...dateSet].sort()
    series = props.compareSeries.map((s, i) => {
      const map = new Map(s.data.map((d) => [d.date, d.price]))
      const color = PALETTE[i % PALETTE.length]
      return {
        name: s.name,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: categories.map((c) => map.get(c) ?? null),
        lineStyle: { width: 2, color, shadowBlur: 6, shadowColor: 'rgba(38, 35, 28, 0.18)' },
        itemStyle: { color },
        emphasis: { focus: 'series' },
      }
    })
  } else {
    categories = props.points.map((p) => p.date)
    const prices = props.points.map((p) => p.price)
    const min = prices.length ? Math.min(...prices) : null
    const max = prices.length ? Math.max(...prices) : null
    const current = prices.length ? prices[prices.length - 1] : null
    series = [
      {
        name: '当日最低价',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: prices,
        // 描线感：墨绿主线 + 轻微墨晕
        lineStyle: { width: 2, color: C.green, shadowBlur: 8, shadowColor: 'rgba(60, 90, 69, 0.28)' },
        itemStyle: { color: C.green },
        markPoint: {
          data: [
            {
              type: 'max',
              name: '最高价',
              itemStyle: { color: C.sage },
              label: { color: C.paper2, fontFamily: MONO, fontSize: 10 },
            },
            {
              type: 'min',
              name: '最低价',
              itemStyle: { color: C.pin },
              label: { color: C.paper2, fontFamily: MONO, fontSize: 10 },
            },
          ],
          symbolSize: 34,
        },
        markLine:
          current != null
            ? {
                data: [{ yAxis: current, name: '当前价' }],
                silent: true,
                symbol: 'none',
                lineStyle: { color: C.lineStrong, type: 'dashed', width: 1 },
                label: { color: C.inkFaint, fontFamily: MONO, fontSize: 10, formatter: '{b} ￥{c}' },
              }
            : undefined,
        areaStyle: { color: 'rgba(60, 90, 69, 0.10)' },
      },
    ]
    void min
    void max
  }

  chart.setOption(
    {
      color: PALETTE,
      animation: true,
      animationDuration: 1600,
      animationEasing: 'cubicOut',
      animationDurationUpdate: 600,
      textStyle: { fontFamily: MONO, color: C.inkFaint },
      title: {
        text: props.title,
        left: 0,
        top: 0,
        textStyle: { fontSize: 13, fontWeight: 600, color: C.inkSoft },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: C.paper2,
        borderColor: C.line,
        borderWidth: 1,
        borderRadius: 3,
        padding: [8, 12],
        textStyle: { color: C.ink, fontSize: 12 },
        extraCssText:
          'box-shadow: 0 2px 4px rgba(70, 58, 36, 0.07), 0 10px 26px rgba(70, 58, 36, 0.09);',
        valueFormatter: (v: any) => (v == null ? '-' : '￥' + v),
      },
      legend: useCompare
        ? { top: 0, right: 0, itemWidth: 16, itemHeight: 3, textStyle: { color: C.inkFaint, fontSize: 11, fontFamily: MONO } }
        : undefined,
      grid: { left: 55, right: 20, top: 50, bottom: 35 },
      xAxis: {
        type: 'category',
        data: categories,
        boundaryGap: false,
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: true, length: 4, lineStyle: { color: C.line } },
        axisLabel: { hideOverlap: true, color: C.inkFaint, fontSize: 10, fontFamily: MONO, margin: 12 },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { formatter: '￥{value}', color: C.inkFaint, fontSize: 10, fontFamily: MONO },
        splitLine: { lineStyle: { color: C.line, type: 'dashed' } },
      },
      series,
    },
    true
  )
}

onMounted(() => {
  chart = echarts.init(el.value!)
  render()
  window.addEventListener('resize', resize)
})
function resize() {
  chart?.resize()
}
onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
// 数据变化（含深层变更）时整体重绘图表
watch(() => [props.points, props.compareSeries], render, { deep: true })
</script>
