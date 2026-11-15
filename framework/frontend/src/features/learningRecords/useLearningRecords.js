import { ref } from 'vue'

export const recordKinds = [
  { id: 'all', label: '全部记录' }, { id: 'dynamic', label: '动态实验' },
  { id: 'simulation', label: '仿真操作' }, { id: 'classic', label: '图形专项' },
  { id: 'lab', label: '专题作答' }, { id: 'legacy', label: '教学练习' },
]
export function scoreText(record = {}) {
  if (typeof record.score === 'number' && Number.isFinite(record.score)) return `${record.score}${typeof record.score_max === 'number' ? ` / ${record.score_max}` : ''} 分`
  return record.score_label || '未评分'
}
export function timeText(value) {
  if (!value) return '—'
  const date = new Date(typeof value === 'number' ? value * 1000 : /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { hour12: false })
}
const actions = {
  PRESS_BUTTON: '按下进路按钮', SWITCH_TOTAL_NORMAL: '道岔总定位', SWITCH_TOTAL_REVERSE: '道岔总反位',
  SWITCH_SINGLE_LOCK: '道岔单锁', SWITCH_SINGLE_UNLOCK: '道岔单解', SWITCH_SEAL: '封闭道岔', SWITCH_UNSEAL: '解封道岔',
  SET_SWITCH_INDICATION: '设置道岔失表示', RESTORE_SWITCH_INDICATION: '恢复道岔表示',
  SET_SECTION_OCCUPANCY: '设置区段占用', CLEAR_SECTION_OCCUPANCY: '恢复区段空闲',
  CANCEL_ROUTE: '取消进路', MANUAL_UNLOCK_ROUTE: '人工解锁', REPEAT_OPEN_SIGNAL: '重复开放信号',
  SECTION_FAULT_UNLOCK: '区段故障解锁', GUIDE_ARM: '办理引导', GUIDE_MAINTAIN: '引导保持',
  GUIDE_TOTAL_LOCK: '引导总锁', GUIDE_TOTAL_UNLOCK: '解除引导总锁',
  SIGNAL_SEAL: '封闭信号机', SIGNAL_UNSEAL: '解封信号机', SIGNAL_LIGHT_ON: '信号点灯', SIGNAL_LIGHT_OFF: '信号灭灯',
  BLOCK_REQUEST: '区间闭塞请求', BLOCK_PEER_ACCEPT: '邻站同意', BLOCK_RESET: '闭塞复原',
  BLOCK_ACCIDENT_RESET: '事故复原', BLOCK_DEPARTURE_AUX: '发车辅助', BLOCK_RECEPTION_AUX: '接车辅助', BLOCK_TOTAL_AUX: '总辅助',
  CLEAR_SELECTION: '清除按钮选择', ADVANCE_TRAIN: '推进模拟行车', SUBMIT: '提交作答',
}
export const operationLabel = value => actions[value] || value || '实验操作'
export const feedbackLabel = source => ({ ai: 'AI教学解析', rules: '规则教学反馈', rules_fallback: '规则教学反馈', teacher: '教师评语', no_errors: '作答反馈' })[source] || '教学反馈'
export const operationCountText = record => `${record.operation_count || 0} ${record.kind === 'lab' ? '项作答' : record.kind === 'classic' ? '次提交' : '次操作'}`
export const errorCountText = record => `${record.error_count || 0} ${record.kind === 'simulation' ? '条操作提示' : '个错误点'}`
const failureText = (failure, fallback) => typeof failure?.response?.data?.detail === 'string' ? failure.response.data.detail : fallback

export function createLearningRecords({ get }) {
  const items = ref([]), counts = ref({}), total = ref(0), kind = ref('all'), page = ref(1)
  const loading = ref(false), error = ref(''), selected = ref(null), detail = ref(null), detailLoading = ref(false), detailError = ref('')
  let listVersion = 0, detailVersion = 0, disposed = false
  async function load() {
    if (disposed) return
    const version = ++listVersion
    loading.value = true; error.value = ''
    try {
      const response = await get('/learning-records', { params: { kind: kind.value, page: page.value, limit: 20 } })
      if (disposed || version !== listVersion) return
      items.value = response.items || []; total.value = response.total || 0; counts.value = response.counts || {}
    } catch (failure) { if (!disposed && version === listVersion) error.value = failureText(failure, '实验记录加载失败，请重试。') }
    finally { if (!disposed && version === listVersion) loading.value = false }
  }
  function close() { detailVersion++; selected.value = null; detail.value = null; detailLoading.value = false; detailError.value = '' }
  function setKind(value) { kind.value = recordKinds.some(item => item.id === value) ? value : 'all'; page.value = 1; close(); return load() }
  function setPage(value) { page.value = Math.max(1, Math.trunc(Number(value)) || 1); close(); return load() }
  async function open(record) {
    if (disposed) return
    const version = ++detailVersion
    selected.value = record; detail.value = null; detailError.value = ''; detailLoading.value = true
    try {
      const response = await get(`/learning-records/${encodeURIComponent(record.kind)}/${encodeURIComponent(record.record_id)}`)
      if (!disposed && version === detailVersion) detail.value = response
    } catch (failure) { if (!disposed && version === detailVersion) detailError.value = failureText(failure, '记录详情加载失败，请重试。') }
    finally { if (!disposed && version === detailVersion) detailLoading.value = false }
  }
  function dispose() { disposed = true; listVersion++; close(); loading.value = false }
  return { items, counts, total, kind, page, loading, error, selected, detail, detailLoading, detailError, load, setKind, setPage, open, close, dispose }
}
