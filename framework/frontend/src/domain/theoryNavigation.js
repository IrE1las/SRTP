export const THEORY_ROOT = '/student/learn/theory'
export function theoryTopicPath(topic) {
  const id = Number(topic)
  if (!Number.isInteger(id) || id < 1 || id > 6) throw new Error('无效理论专题')
  return THEORY_ROOT + '/' + id
}
export function theoryPlatform(topic) {
  theoryTopicPath(topic)
  return Number(topic) <= 4 ? 'simulation-console' : 'interlocking-table'
}
export const theoryPlatformName = topic => theoryPlatform(topic) === 'simulation-console' ? '联锁仿真操作台' : '联锁表仿真平台'
export function theoryHistoryPath(topic = 1) {
  theoryTopicPath(topic)
  return { path: THEORY_ROOT + '/attempts', query: { topic: String(topic) } }
}
