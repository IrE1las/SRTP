import topology from '../../../../ai_design/station/station_topology.json'

// Geometry follows the circled photograph; device semantics come from the existing topology.
export { topology }
export const canvasSize = { width: 1700, height: 830 }
const anchors = [[0, 90], [1, 250], [3, 420], [3.5, 470], [4, 520], [4.5, 580], [5, 650], [7, 785], [7.5, 850], [8.5, 965], [9, 1055], [9.5, 1110], [10, 1170], [10.5, 1230], [11.5, 1340], [12.5, 1405], [15, 1500], [17, 1650]]
export function mapX(value) {
  const upper = anchors.findIndex(([x]) => x >= value)
  if (upper <= 0) return anchors[0][1]
  const [a, b] = [anchors[upper - 1], anchors[upper]]
  return a[1] + (value - a[0]) / (b[0] - a[0]) * (b[1] - a[1])
}
const ys = { '5': 155, 'III': 305, 'I': 465, 'II': 630, '4': 760 }
export const tracks = topology.tracks.map(t => ({ ...t, y: ys[t.id], start: mapX(t.exists_x_range[0]), end: mapX(17) }))
const point = s => ({ x: mapX(s.x), y: ys[s.track], label: s.id.replace('#', '') })
export const switches = topology.switches.map(s => ({
  ...s, a: point(s.switch_a), b: s.switch_b ? point(s.switch_b) : { x: mapX(s.side_x), y: ys[s.side_track] },
}))
export const signals = topology.signals.map(s => {
  const terminal = topology.tracks.find(t => t.terminal_signal === s.name)
  const buttons = new Set([s.name + s.button_suffix])
  if (terminal) buttons.add(s.name + terminal.terminal_button_type)
  // Drawing-side placement and mechanism symbols transcribed individually from the photo.
  const photoSymbols = { XD: 'XD', X: 'X', S5: 'S5', SIII: 'S5', SII: 'SII', S4: 'S5' }
  const below = ['D5', 'D7', 'D17', 'S5', 'SIII', 'SII', 'S4'].includes(s.name)
  const symbol = photoSymbols[s.name] || 'D'
  // Keep the photographed glyphs close to their rails. The two-row photo pattern
  // needs a slightly larger center offset to retain the same small edge clearance.
  const offset = below ? (symbol === 'S5' ? 30 : 24) : -24
  const width = ['X', 'XD'].includes(symbol) ? 112 : symbol === 'SII' ? 85 : symbol === 'S5' ? 55 : 34
  const hitbox = { x: s.direction === 1 ? -48 : -width - 4, width: s.direction === 1 ? width + 48 : width + 59,
    ...(symbol === 'S5' ? { y: -20, height: 41 } : { y: -13, height: 26 }) }
  return { ...s, x: mapX(s.x), trackY: ys[s.track], y: ys[s.track] + offset, symbol, symbolWidth: width, hitbox, buttons: [...buttons], shuntFunction: s.type === '出站' ? s.name + 'D' : null }
})
// The photo also shows a signal absent from the local numbered inventory. Preserve a
// descriptive choice so it is interactive without inventing a formal device code.
export const photoSignalCode = '原图预告信号'
export const photoSignalPosition = { x: 92, y: ys.III - 24 }
export const signalChoices = [...signals.flatMap(s => [s.name, ...(s.shuntFunction ? [s.shuntFunction] : [])]), photoSignalCode]
export const routeButtons = [...new Set([...signals.flatMap(s => s.buttons), 'SLZA'])]
export const sections = topology.sections.map(s => {
  const start = mapX(s.x_start), end = mapX(s.x_end ?? 17), y = ys[s.track]
  const segments = [[start, y, end, y]]
  for (const sw of switches) {
    if (!sw.switch_b) {
      if (sw.side_covered_by_section === s.name) {
        segments.push([sw.a.x, sw.a.y, sw.b.x, sw.b.y], [sw.b.x, sw.b.y, mapX(15), sw.b.y])
      }
    } else {
      const mid = { x: (sw.a.x + sw.b.x) / 2, y: (sw.a.y + sw.b.y) / 2 }
      if (topology.switch_section_mapping[sw.switch_a.id] === s.name) segments.push([sw.a.x, sw.a.y, mid.x, mid.y])
      if (topology.switch_section_mapping[sw.switch_b.id] === s.name) segments.push([mid.x, mid.y, sw.b.x, sw.b.y])
    }
  }
  // Keep the below-rail track-section labels clear of terminal signal names.
  return { ...s, x: s.x_end == null && ['III', 'I', 'II'].includes(s.track) ? 1600 : (start + end) / 2, y, labelY: y + (s.track === '5' || s.track === '4' ? -25 : 28), segments }
})
export const exams = {
  dongjiao_to_III: { index: '01', title: '办理一条由东郊方面至 III 股道的接车进路', subtitle: '东郊方面 → III 股道', topic: '基础进路', route: '/student/interlocking-exam' },
  dongjiao_to_I: { index: '02', title: '办理一条由东郊方面至 I 股道的接车进路', subtitle: '东郊方面 → I 股道', topic: '防护道岔', route: '/student/interlocking-exam-protective' },
  dongjiao_to_4: { index: '03', title: '办理一条由东郊方面至 4 股道的接车进路', subtitle: '东郊方面 → 4 股道', topic: '带动道岔', route: '/student/interlocking-exam-driven' },
  beijing_depart_5: { index: '04', title: '办理一条由 5 股道向北京方面的发车进路', subtitle: '5 股道 → 北京方面', topic: '条件区段', route: '/student/interlocking-exam-conditional', conditions: { '23/25': 'normal', '5/7': 'normal' } },
}

export function emptyAnswer(routeType) {
  return { route_type: routeType, route_buttons: [], switches: {}, hostile_signals: [], track_sections: [] }
}
export function copyAnswer(answer) { return JSON.parse(JSON.stringify(answer)) }
export function devicePosition(kind, code) {
  if (code === photoSignalCode) return photoSignalPosition
  if (kind === 'switches') { const s = switches.find(s => s.id === code); return s && s.a }
  if (kind === 'track_sections') return sections.find(s => s.name === code)
  if (code === 'SLZA') return { x: 155, y: 687 }
  return signals.find(s => s.name === code || s.shuntFunction === code || s.buttons.includes(code))
}
