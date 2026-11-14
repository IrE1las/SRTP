const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const dimension = value => Number.isFinite(value) ? Math.max(1, value) : 1

// Perspective coordinates shared by rails, sleepers and the train lights.
export function railwayPoint(width, height, lane, depth, pointer) {
  width = dimension(width); height = dimension(height)
  const t = clamp(Number.isFinite(depth) ? depth : 0, 0, 1.2)
  const shiftX = pointer?.active ? clamp(pointer.x / width - 0.5, -0.5, 0.5) * 40 : 0
  const shiftY = pointer?.active ? clamp(pointer.y / height - 0.5, -0.5, 0.5) * 16 : 0
  const spread = t ** 1.55
  return {
    x: width * 0.5 + shiftX * (1 - t * 0.5) + lane * width * 0.65 * spread,
    y: height * 0.48 + shiftY + height * 0.66 * t ** 1.45,
    gauge: 2 + width * 0.038 * spread,
  }
}

export function createParticleField(width, height, random = Math.random) {
  width = dimension(width); height = dimension(height)
  const count = clamp(Math.round(width * height / 7600), 24, 96)
  return { width, height, particles: Array.from({ length: count }, () => {
    const driftX = 0.13 + random() * 0.16, driftY = -0.05 - random() * 0.11
    return { x: random() * width, y: random() * height, vx: driftX, vy: driftY,
      driftX, driftY, size: 0.8 + random() * 1.5, phase: random() * Math.PI * 2 }
  }) }
}

export function stepParticleField(field, elapsed, pointer, time) {
  const step = clamp(Number.isFinite(elapsed) ? elapsed : 0, 0, 48) / (1000 / 60)
  for (const p of field.particles) {
    const flow = Math.sin(time * 0.00025 + p.phase + p.y / field.height * 2)
    p.vx += (p.driftX + flow * 0.07 - p.vx) * 0.025 * step
    p.vy += (p.driftY + Math.cos(time * 0.0002 + p.phase) * 0.06 - p.vy) * 0.025 * step
    if (pointer?.active) {
      const dx = pointer.x - p.x, dy = pointer.y - p.y, distance = Math.hypot(dx, dy)
      if (distance > 1 && distance < 190) {
        const strength = (1 - distance / 190) ** 2 * step
        p.vx += (dx / distance * 0.035 - dy / distance * 0.012) * strength
        p.vy += (dy / distance * 0.035 + dx / distance * 0.012) * strength
      }
    }
    p.vx = clamp(p.vx, -0.8, 0.8); p.vy = clamp(p.vy, -0.8, 0.8)
    p.x = ((p.x + p.vx * step) % field.width + field.width) % field.width
    p.y = ((p.y + p.vy * step) % field.height + field.height) % field.height
  }
}
