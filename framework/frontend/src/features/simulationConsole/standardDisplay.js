// TB/T 3578—2022, appendix A, table A.1 (supplied PDF, printed page 17).
export const COLORS = Object.freeze({
  background: '#000000', red: '#ff0000', green: '#00ff00', darkGreen: '#008000',
  blue: '#0000ff', darkBlue: '#5050cd', brightBlue: '#3c42eb', idle: '#5578b6',
  white: '#ffffff', lightGray: '#efefef', silver: '#c0c0c0', gray: '#808080',
  yellow: '#ffff00', shuntFault: '#bc43b4',
})
export function sectionColor(state) {
  return state?.occupied ? COLORS.red : state?.locked ? COLORS.white : COLORS.idle
}
export function lampColors(isShunt, aspect, lit = true) {
  if (!lit) return [COLORS.background, COLORS.background]
  if (isShunt) return [aspect === 'B' ? COLORS.white : COLORS.blue]
  return ({ U: [COLORS.background, COLORS.yellow], UU: [COLORS.yellow, COLORS.yellow],
    L: [COLORS.background, COLORS.green], B: [COLORS.white, COLORS.background], HB: [COLORS.red, COLORS.white] })[aspect]
    || [COLORS.red, COLORS.background]
}
export const COMMANDS = [
  { label: '总取消', type: 'CANCEL_ROUTE', target: 'route', icon: 'QX' },
  { label: '总人解', type: 'MANUAL_UNLOCK_ROUTE', target: 'route', sealed: true, icon: 'RJ' },
  { label: '区故解', type: 'SECTION_FAULT_UNLOCK', target: 'section', referenceOnly: true, sealed: true, icon: 'SGJS' },
  { label: '引导', type: 'GUIDE_ARM', target: 'signal', referenceOnly: true, sealed: true, icon: 'SignalYD' },
  { label: '引导保持', type: 'GUIDE_MAINTAIN', target: 'signal', referenceOnly: true, icon: 'SignalYD' },
  { label: '引导总锁', type: 'GUIDE_TOTAL_LOCK', target: 'signal', referenceOnly: true, sealed: true, icon: 'DS' },
  { label: '解除引总锁', type: 'GUIDE_TOTAL_UNLOCK', target: 'signal', referenceOnly: true, sealed: true, icon: 'DJ' },
  { label: '总定位', type: 'SWITCH_TOTAL_NORMAL', target: 'switch', icon: 'ZD' },
  { label: '总反位', type: 'SWITCH_TOTAL_REVERSE', target: 'switch', icon: 'ZF' },
  { label: '清除', type: 'CLEAR_SELECTION', icon: 'ClrBtn' },
  { label: '单锁', type: 'SWITCH_SINGLE_LOCK', target: 'switch', icon: 'DS' },
  { label: '单解', type: 'SWITCH_SINGLE_UNLOCK', target: 'switch', icon: 'DJ' },
  { label: '按钮封锁', type: 'SIGNAL_SEAL', target: 'signal', sealed: true, icon: 'FB' },
  { label: '按钮解封', type: 'SIGNAL_UNSEAL', target: 'signal', sealed: true, icon: 'JF' },
  { label: '道岔封锁', type: 'SWITCH_SEAL', target: 'switch', icon: 'FB' },
  { label: '道岔解封', type: 'SWITCH_UNSEAL', target: 'switch', icon: 'JF' },
  { label: '点灯', type: 'SIGNAL_LIGHT_ON', target: 'signal', icon: 'Signal' },
  { label: '灭灯', type: 'SIGNAL_LIGHT_OFF', target: 'signal', sealed: true, icon: 'Signal' },
  { label: '重开信号', type: 'REPEAT_OPEN_SIGNAL', target: 'route', icon: 'CKXH' },
]
