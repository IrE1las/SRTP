import test from 'node:test'
import assert from 'node:assert/strict'
import { navigationGroups, pageLabel } from '../src/ui/navigation.js'

test('student learning navigation has three ordered learning destinations and a separate record entry', () => {
  const groups = navigationGroups('student')
  assert.deepEqual(groups[0].items.map(item => item.title), ['客观题库', '实验专题', '仿真操作台'])
  assert.deepEqual(groups[1].items.map(item => item.title), ['实验学习记录'])
  assert.equal(groups.flatMap(group => group.items).some(item => item.path === '/student/modules' || item.path.includes('interlocking-exam')), false)
})

test('admin navigation contains only platform management and account while teacher tools remain available', () => {
  const groups = navigationGroups('admin')
  assert.deepEqual(groups.map(group => group.title), ['平台管理', '账号'])
  assert.deepEqual(groups.flatMap(group => group.items).map(item => item.path), ['/admin', '/admin/users', '/admin/ai-settings', '/admin/knowledge', '/account'])
  assert.ok(navigationGroups('teacher').flatMap(group => group.items).some(item => item.path === '/teacher/grading'))
})

test('six-topic routes and the complete question table have meaningful labels', () => {
  assert.equal(pageLabel('/student/chapter-bank/all','student'),'全部题目')
  assert.equal(pageLabel('/student/lab-topics','student'),'实验专题')
  assert.equal(pageLabel('/student/history','student'),'实验学习记录')
})
