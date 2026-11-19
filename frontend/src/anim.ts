/**
 * 标本手记 · 动效工具（GSAP 编排）
 * 约定：优先 transform/opacity；prefers-reduced-motion 或无 gsap 时直出终态。
 */
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

export const reducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** 标题字符级遮罩揭示：把元素文本逐字包 span 并编排入场 */
export function splitReveal(el: HTMLElement | null, delay = 0) {
  if (!el) return
  const text = el.textContent || ''
  el.setAttribute('aria-label', text)
  el.innerHTML = text
    .split('')
    .map((c) =>
      c.trim() === ''
        ? '<span class="ch" style="display:inline-block;width:.32em">&nbsp;</span>'
        : `<span class="ch">${c}</span>`
    )
    .join('')
  el.classList.add('reveal-mask')
  const chars = el.querySelectorAll<HTMLElement>('.ch')
  if (reducedMotion) {
    el.classList.add('in')
    chars.forEach((c) => (c.style.transform = 'none'))
    return
  }
  gsap.fromTo(
    chars,
    { yPercent: 110 },
    {
      yPercent: 0,
      duration: 0.9,
      delay,
      stagger: 0.025,
      ease: 'power4.out',
      onComplete: () => el.classList.add('in'),
    }
  )
}

/** 找到元素实际所在的滚动容器（布局页在内层 overflow 容器里滚动，ScrollTrigger 需显式指定 scroller，否则永远监听 window 不触发） */
function findScroller(el: HTMLElement): Element | Window {
  let node: HTMLElement | null = el.parentElement
  while (node) {
    const oy = getComputedStyle(node).overflowY
    if ((oy === 'auto' || oy === 'scroll') && node.scrollHeight > node.clientHeight + 10) return node
    node = node.parentElement
  }
  return window
}

/** 滚动入场：区块进入视口时错落浮现 */
export function revealOnScroll(root: ParentNode = document) {
  const els = Array.from(root.querySelectorAll<HTMLElement>('.reveal'))
  if (reducedMotion) {
    els.forEach((el) => el.classList.add('in'))
    return
  }
  els.forEach((el) => {
    if (el.classList.contains('in')) return
    if ((el as any).__revealTrigger) (el as any).__revealTrigger.kill()
    ;(el as any).__revealTrigger = ScrollTrigger.create({
      trigger: el,
      scroller: findScroller(el),
      start: 'top 82%',
      once: true,
      onEnter: () => {
        const delay = parseInt(el.dataset.delay || '0', 10) / 1000
        gsap.to(el, {
          opacity: 1,
          y: 0,
          duration: 0.85,
          delay,
          ease: 'power4.out',
          onComplete: () => el.classList.add('in'),
        })
      },
    })
  })
}

/** 数字 count-up（带千分位；el.dataset.count 为目标值，dataset.prefix/suffix 可选） */
export function countUp(el: HTMLElement | null) {
  if (!el || el.dataset.counted === '1') return
  el.dataset.counted = '1'
  const target = parseFloat(el.dataset.count || '0')
  const prefix = el.dataset.prefix || ''
  const suffix = el.dataset.suffix || ''
  const fmt = (n: number) =>
    prefix + Math.round(n).toLocaleString('en-US') + suffix
  if (reducedMotion || !gsap) {
    el.textContent = fmt(target)
    return
  }
  const obj = { v: 0 }
  gsap.to(obj, {
    v: target,
    duration: 1.6,
    ease: 'power3.out',
    onUpdate: () => (el.textContent = fmt(obj.v)),
  })
}

/** 滚动视差：元素随滚动以不同速率位移 */
export function parallax(el: HTMLElement | null, yPercent = 10) {
  if (!el || reducedMotion) return
  gsap.to(el, {
    yPercent,
    ease: 'none',
    scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: true },
  })
}

/** 磁性按钮：mousemove 跟随 + 回弹 */
export function magnetic(el: HTMLElement | null) {
  if (!el || reducedMotion) return
  const xTo = gsap.quickTo(el, 'x', { duration: 0.35, ease: 'power3.out' })
  const yTo = gsap.quickTo(el, 'y', { duration: 0.35, ease: 'power3.out' })
  el.addEventListener('mousemove', (e: MouseEvent) => {
    const r = el.getBoundingClientRect()
    xTo((e.clientX - r.left - r.width / 2) * 0.28)
    yTo((e.clientY - r.top - r.height / 2) * 0.28)
  })
  el.addEventListener('mouseleave', () => {
    gsap.to(el, { x: 0, y: 0, duration: 0.6, ease: 'back.out(1.7)' })
  })
}

/** 卡片 3D 悬浮：悬停浮起 + 跟随鼠标倾斜 + 光斑跟随 */
export function tiltCard(el: HTMLElement | null) {
  if (!el || reducedMotion) return
  const xTo = gsap.quickTo(el, 'rotationY', { duration: 0.4, ease: 'power3.out' })
  const yTo = gsap.quickTo(el, 'rotationX', { duration: 0.4, ease: 'power3.out' })
  const liftTo = gsap.quickTo(el, 'y', { duration: 0.35, ease: 'power2.out' })
  const scaleTo = gsap.quickTo(el, 'scale', { duration: 0.35, ease: 'power2.out' })
  gsap.set(el, { transformPerspective: 800 })
  el.addEventListener('mouseenter', () => {
    liftTo(-10) // 悬停浮起
    scaleTo(1.03)
  })
  el.addEventListener('mousemove', (e: MouseEvent) => {
    const r = el.getBoundingClientRect()
    xTo(((e.clientX - r.left) / r.width - 0.5) * 12) // 倾斜角度跟随鼠标
    yTo(-((e.clientY - r.top) / r.height - 0.5) * 12)
    el.style.setProperty('--gx', `${((e.clientX - r.left) / r.width) * 100}%`)
    el.style.setProperty('--gy', `${((e.clientY - r.top) / r.height) * 100}%`)
  })
  el.addEventListener('mouseleave', () => {
    gsap.to(el, {
      rotationX: 0, rotationY: 0, y: 0, scale: 1,
      duration: 0.7, ease: 'back.out(1.7)',
    })
  })
}

/** SVG 描线动画（path/polyline 通用） */
export function drawLine(el: SVGGeometryElement | null, duration = 1.8) {
  if (!el) return
  if (reducedMotion) {
    el.style.strokeDasharray = 'none'
    el.style.strokeDashoffset = '0'
    return
  }
  const len = el.getTotalLength()
  gsap.fromTo(
    el,
    { strokeDasharray: `${len} ${len}`, strokeDashoffset: len },
    { strokeDashoffset: 0, duration, ease: 'power2.inOut' }
  )
}

/** 弹性入场（签名时刻用） */
export function popIn(el: HTMLElement | null, delay = 0) {
  if (!el) return
  if (reducedMotion) {
    el.style.opacity = '1'
    return
  }
  gsap.fromTo(
    el,
    { scale: 0.55, opacity: 0, rotate: -8 },
    { scale: 1, opacity: 1, rotate: 0, duration: 0.9, delay, ease: 'back.out(1.8)' }
  )
}

/** 图钉 squash 按入（标本手记签名时刻） */
export function pinPress(el: HTMLElement | null, delay = 0) {
  if (!el) return
  if (reducedMotion) {
    el.style.opacity = '1'
    return
  }
  gsap.fromTo(
    el,
    { scale: 1.8, opacity: 0, y: -10 },
    {
      scale: 1,
      opacity: 1,
      y: 0,
      duration: 0.65,
      delay,
      ease: 'back.out(2.4)',
      onComplete: () => {
        gsap.fromTo(el, { scaleY: 0.72 }, { scaleY: 1, duration: 0.35, ease: 'elastic.out(1,0.45)' })
      },
    }
  )
}

/** 刷新 ScrollTrigger（路由切换/异步内容后调用） */
export function refreshScroll() {
  ScrollTrigger.refresh()
}

/** 重扫 root 内未绑定的 .reveal（异步挂载内容后调用；已绑定的自动跳过） */
export function rescanReveals(root: ParentNode = document) {
  revealOnScroll(root)
  ScrollTrigger.refresh()
}
