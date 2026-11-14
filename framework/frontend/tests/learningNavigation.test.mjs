import test from 'node:test'
import assert from 'node:assert/strict'
import { navigationGroups, pageLabel } from '../src/ui/navigation.js'

test('student learning navigation has three ordered learning destinations and a separate record entry', () => {
  const groups = navigationGroups('student')
  assert.deepEqual(groups[0].items.map(item => item.title), ['客观题库', '实验专题', '仿真操作台'])
  assert.deepEqual(groups[1].items.map(item => item.title), ['实验学习记录'])
  assert.equal(groups.flatMap(group => group.items).some(item => item.path === '/student/modules' || item.path.includes('interlocking-exam')), false)
})

test('admin study navigation uses the same learning order while teaching and authoring tools remain available', () => {
  const groups = navigationGroups('admin')
  assert.deepEqual(groups[0].items.map(item => item.title), ['客观题库', '实验专题', '仿真操作台'])
  assert.ok(groups.flatMap(group => group.items).some(item => item.path === '/admin/questions'))
  assert.ok(navigationGroups('teacher').flatMap(group => group.items).some(item => item.path === '/teacher/grading'))
})

test('old content routes retain meaningful labels after their duplicate navigation entries are removed', () => {
  assert.equal(pageLabel('/student/interlocking-exam-protective', 'student'), '防护道岔')
  assert.equal(pageLabel('/student/modules/one/experiment-1', 'student'), '动态操作实验')
  assert.equal(pageLabel('/student/history', 'student'), '实验学习记录')
})
