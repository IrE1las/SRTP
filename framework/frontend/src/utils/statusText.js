const sessionStatusMap = {
  ongoing: '进行中',
  completed: '已完成',
  timeout: '已超时',
  aborted: '已终止',
}

const completionStatusMap = {
  success: '成功',
  failed: '失败',
  timeout: '超时',
}

const operationTypeMap = {
  select_route: '办理进路',
  operate_switch: '单操道岔',
  toggle_section: '区段占用/出清',
  cancel_route: '取消进路',
  manual_unlock: '人工解锁',
  timeout_auto_finish: '超时结束',
}

const difficultyMap = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

export function sessionStatusText(value) {
  return sessionStatusMap[value] || value || '-'
}

export function completionStatusText(value) {
  return completionStatusMap[value] || value || '-'
}

export function operationTypeText(value) {
  return operationTypeMap[value] || value || '-'
}

export function difficultyText(value) {
  return difficultyMap[value] || value || '-'
}
