<template><canvas ref="canvas" class="login-particle-canvas" aria-hidden="true" /></template>
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { createParticleField, stepParticleField, railwayPoint } from './particleField.js'

const canvas = ref(null)
let context, surface, field, observer, motion, frame = 0, lastTime = 0
const pointer = { x: 0, y: 0, targetX: 0, targetY: 0, active: false }

function draw(time = 0) {
  if (!context || !field) return
  const { width, height, particles } = field
  context.clearRect(0, 0, width, height)
  const point = (lane, depth) => railwayPoint(width, height, lane, depth, pointer)
  for (const lane of [-1, 1]) {
    // Two rails with regularly spaced sleepers, converging into the distance.
    for (const edge of [-1, 1]) {
      context.beginPath()
      for (let i = 0; i <= 64; i++) {
        const p = point(lane, i / 64 * 1.12)
        const x = p.x + p.gauge * edge
        if (i === 0) context.moveTo(x, p.y)
        else context.lineTo(x, p.y)
      }
      const rail = context.createLinearGradient(0, height * 0.48, 0, height)
      rail.addColorStop(0, 'rgba(160, 221, 255, 0)')
      rail.addColorStop(0.35, 'rgba(168, 228, 255, 0.3)')
      rail.addColorStop(1, 'rgba(187, 236, 255, 0.65)')
      context.strokeStyle = rail; context.lineWidth = 1.2; context.stroke()
    }
    for (let i = 1; i <= 26; i++) {
      const depth = i / 26 * 1.12, p = point(lane, depth)
      context.beginPath(); context.moveTo(p.x - p.gauge * 1.4, p.y)
      context.lineTo(p.x + p.gauge * 1.4, p.y)
      context.strokeStyle = `rgba(161, 217, 255, ${depth * 0.25})`
      context.lineWidth = 0.7 + depth; context.stroke()
    }
    // Light carriages follow the rail geometry, rather than drifting freely.
    const depth = 0.22 + ((time * 0.000035 + (lane === -1 ? 0.38 : 0.78)) % 1) * 0.9
    for (let car = 3; car >= 0; car--) {
      const front = point(lane, depth - car * 0.058)
      const back = point(lane, depth - car * 0.058 - 0.048)
      const lift = front.gauge * 0.75
      context.beginPath()
      context.moveTo(front.x - front.gauge * 0.65, front.y - lift)
      context.lineTo(back.x - back.gauge * 0.65, back.y - back.gauge * 0.75)
      context.lineTo(back.x + back.gauge * 0.65, back.y - back.gauge * 0.75)
      context.lineTo(front.x + front.gauge * 0.65, front.y - lift)
      context.closePath()
      context.fillStyle = 'rgba(158, 222, 255, 0.12)'; context.fill()
      context.strokeStyle = `rgba(201, 242, 255, ${0.3 + depth * 0.35})`
      context.lineWidth = 1; context.stroke()
      // A blue window band makes the light train recognizable at close range.
      context.beginPath()
      context.moveTo(back.x, back.y - back.gauge * 0.85)
      context.lineTo(front.x, front.y - lift * 1.1)
      context.strokeStyle = 'rgba(107, 205, 255, 0.6)'
      context.lineWidth = Math.max(1, front.gauge * 0.16); context.stroke()
    }
    const head = point(lane, depth)
    for (const side of [-1, 1]) {
      const x = head.x + side * head.gauge * 0.43, y = head.y - head.gauge * 0.6
      const glow = context.createRadialGradient(x, y, 0, x, y, head.gauge * 2.6)
      glow.addColorStop(0, 'rgba(207, 246, 255, 0.55)')
      glow.addColorStop(1, 'rgba(123, 216, 255, 0)')
      context.fillStyle = glow
      context.fillRect(x - head.gauge * 3, y - head.gauge * 3, head.gauge * 6, head.gauge * 6)
      context.beginPath(); context.arc(x, y, 1 + depth * 1.6, 0, Math.PI * 2)
      context.fillStyle = '#e3f8ff'; context.fill()
    }
    // Small light signals move along the same rails, including on narrow screens.
    for (let i = 0; i < 12; i++) {
      const t = (time * 0.000055 + i / 12 + (lane === 1 ? 0.04 : 0)) % 1
      const p = point(lane, t), tail = point(lane, Math.max(0, t - 0.035))
      context.beginPath(); context.moveTo(tail.x - tail.gauge, tail.y)
      context.lineTo(p.x - p.gauge, p.y)
      context.strokeStyle = `rgba(190, 238, 255, ${t * 0.65})`
      context.lineWidth = 1.5; context.stroke()
    }
  }
  // Sparse floating specks soften the scene without a constellation mesh.
  for (const p of particles) {
    context.beginPath(); context.arc(p.x, p.y, p.size * 0.65, 0, Math.PI * 2)
    context.fillStyle = `rgba(224, 246, 255, ${0.14 + (Math.sin(time * 0.0009 + p.phase) + 1) * 0.12})`
    context.fill()
  }
}

function animate(time) {
  if (pointer.active) {
    pointer.x += (pointer.targetX - pointer.x) * 0.07
    pointer.y += (pointer.targetY - pointer.y) * 0.07
  }
  stepParticleField(field, lastTime ? time - lastTime : 16, motion.matches ? null : pointer, time)
  lastTime = time; draw(time)
  frame = requestAnimationFrame(animate)
}
function restart() {
  cancelAnimationFrame(frame); frame = 0; lastTime = 0
  if (!field) return
  draw()
  if (!motion.matches && !document.hidden) frame = requestAnimationFrame(animate)
}
function resize() {
  const rect = surface.getBoundingClientRect(), ratio = Math.min(window.devicePixelRatio || 1, 2)
  if (!rect.width || !rect.height) return
  canvas.value.width = Math.round(rect.width * ratio); canvas.value.height = Math.round(rect.height * ratio)
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  field = createParticleField(rect.width, rect.height)
  pointer.active = false; restart()
}
function move(event) {
  if (motion.matches || event.pointerType === 'touch') return
  const rect = surface.getBoundingClientRect()
  pointer.targetX = event.clientX - rect.left; pointer.targetY = event.clientY - rect.top
  if (!pointer.active) { pointer.x = pointer.targetX; pointer.y = pointer.targetY }
  pointer.active = true
}
function leave() { pointer.active = false }
onMounted(() => {
  context = canvas.value.getContext('2d')
  if (!context) return
  surface = canvas.value.parentElement
  motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  observer = new ResizeObserver(resize); observer.observe(surface)
  surface.addEventListener('pointermove', move, { passive: true })
  surface.addEventListener('pointerleave', leave, { passive: true })
  motion.addEventListener('change', restart); document.addEventListener('visibilitychange', restart)
  resize()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame); observer?.disconnect()
  surface?.removeEventListener('pointermove', move); surface?.removeEventListener('pointerleave', leave)
  motion?.removeEventListener('change', restart); document.removeEventListener('visibilitychange', restart)
})
</script>
<style scoped>
.login-particle-canvas{position:absolute;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none}
</style>
