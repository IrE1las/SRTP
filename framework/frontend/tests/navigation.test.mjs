import test from 'node:test'
import assert from 'node:assert/strict'
import { navigationForRole, navigationGroups, roleHomeMap } from '../src/ui/navigation.js'

test('student navigation has exactly three ordered roots and two study children', () => {
  const nav = navigationForRole('student')
  assert.deepEqual(nav.map(i=>i.title), ['首页','学习界面','考试界面'])
  assert.equal(nav[0].children, undefined)
  assert.deepEqual(nav[1].children.map(i=>i.title), ['理论学习','操作学习'])
  assert.deepEqual(nav[2].children, [{title:'历史考试',path:'/student/exams/history'}])
  assert.equal(nav[2].overview, true)
})
test('teacher and administrator have separate role menus', () => {
  assert.deepEqual(navigationForRole('teacher').map(i=>i.title), ['首页','题目管理','考试管理'])
  assert.deepEqual(navigationForRole('admin').map(i=>i.title), ['首页','用户管理','AI设置'])
  for (const role of ['student','teacher','admin']) {
    assert.equal(navigationForRole(role)[0].path,roleHomeMap[role])
    const paths = navigationGroups(role)[0].items.map(i=>i.path)
    assert.equal(paths.length, new Set(paths).size)
    assert.ok(paths.every(p=>p.startsWith('/'+role) || role==='teacher' && p==='/operations/manage'))
  }
  assert.deepEqual(navigationForRole('unknown'), [])
})

test('teachers have distinct theory and operation navigation under question management', () => {
  assert.deepEqual(navigationForRole('teacher')[1].children, [{title:'理论学习',path:'/teacher/questions'},{title:'操作学习',path:'/operations/manage'}])
})
