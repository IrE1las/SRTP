import test from 'node:test'
import assert from 'node:assert/strict'
import { createParticleField, stepParticleField, railwayPoint } from '../src/features/login/particleField.js'

test('railway tracks converge at the horizon and widen towards the viewer', () => {
  for (const width of [320, 1440]) {
    const horizon = railwayPoint(width, 900, -1, 0)
    assert.deepEqual(horizon, railwayPoint(width, 900, 1, 0))
    const near = railwayPoint(width, 900, -1, 0.85)
    const far = railwayPoint(width, 900, -1, 0.2)
    assert.ok(near.y > far.y && near.gauge > far.gauge && near.x < far.x)
    const moved = railwayPoint(width, 900, -1, 0.85, { active: true, x: width, y: 450 })
    assert.ok(moved.x > near.x && moved.x - near.x <= 20)
  }
})

test('particle density stays bounded on phones and large displays', () => {
  const phone = createParticleField(390, 180)
  const desktop = createParticleField(800, 1000)
  const large = createParticleField(6000, 4000)
  assert.ok(phone.particles.length < desktop.particles.length)
  assert.ok(large.particles.length <= 96)
  for (const field of [phone, desktop, large]) for (const p of field.particles) {
    assert.ok(p.x >= 0 && p.x <= field.width && p.y >= 0 && p.y <= field.height)
  }
})

test('a nearby pointer bends the flow towards the pointer while distant points keep their drift', () => {
  const idle = createParticleField(700, 800, () => 0.5)
  const interactive = structuredClone(idle)
  const pointer = { x: 420, y: 420, active: true }
  for (let i = 0; i < 40; i++) {
    stepParticleField(idle, 16, null, i * 16)
    stepParticleField(interactive, 16, pointer, i * 16)
  }
  const distance = p => Math.hypot(p.x - pointer.x, p.y - pointer.y)
  assert.ok(distance(interactive.particles[0]) < distance(idle.particles[0]))
  const far = createParticleField(700, 800, () => 0.5), control = structuredClone(far)
  stepParticleField(far, 16, { x: -1000, y: -1000, active: true }, 16)
  stepParticleField(control, 16, null, 16)
  assert.deepEqual(far, control)
})

test('resuming after a long frame gap keeps particles finite and inside the cover', () => {
  const field = createParticleField(390, 180)
  for (let i = 0; i < 200; i++) stepParticleField(field, 120000, { x: 200, y: 70, active: true }, i * 120000)
  for (const p of field.particles) {
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y))
    assert.ok(p.x >= 0 && p.x < field.width && p.y >= 0 && p.y < field.height)
    assert.ok(Math.abs(p.vx) <= 0.8 && Math.abs(p.vy) <= 0.8)
  }
})
