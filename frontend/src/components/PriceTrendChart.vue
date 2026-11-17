<template>
  <div ref="el" :style="{ height: height + 'px', width: '100%' }"></div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = withDefaults(
  defineProps<{
    points: { date: string; price: number; platform?: string }[]
    height?: number
    title?: string
    compareSeries?: { name: string; data: { date: string; price: number }[] }[]
  }>(),
  { height: 300, title: '历史价格走势', compareSeries: () => [] }
)

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chart) return
  const useCompare = props.compareSeries.length > 0
  let series: any[]
  let categories: string[]

  if (useCompare) {
    const dateSet = new Set<string>()
    props.compareSeries.forEach((s) => s.data.forEach((d) => dateSet.add(d.date)))
    categories = [...dateSet].sort()
    series = props.compareSeries.map((s) => {
      const map = new Map(s.data.map((d) => [d.date, d.price]))
      return {
        name: s.name,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: categories.map((c) => map.get(c) ?? null),
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
        markPoint: {
          data: [
            { type: 'max', name: '最高价' },
            { type: 'min', name: '最低价' },
          ],
        },
        markLine: current != null ? { data: [{ yAxis: current, name: '当前价' }], silent: true } : undefined,
        areaStyle: { opacity: 0.12 },
      },
    ]
    void min
    void max
  }

  chart.setOption(
    {
      title: { text: props.title, left: 0, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis', valueFormatter: (v: any) => (v == null ? '-' : '￥' + v) },
      legend: useCompare ? { top: 0, right: 0 } : undefined,
      grid: { left: 55, right: 20, top: 50, bottom: 35 },
      xAxis: { type: 'category', data: categories, axisLabel: { hideOverlap: true } },
      yAxis: { type: 'value', axisLabel: { formatter: '￥{value}' } },
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
watch(() => [props.points, props.compareSeries], render, { deep: true })
</script>
