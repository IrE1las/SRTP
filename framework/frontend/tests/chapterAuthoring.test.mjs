import test from 'node:test'
import assert from 'node:assert/strict'
import { emptyChapterQuestion, chapterPayload, removeChapterOption } from '../src/domain/chapterAuthoring.js'
import { navigationGroups, teacherDestination, pageLabel } from '../src/ui/navigation.js'
test('teacher navigation provides management destinations and removes the circled learning tools',()=>{
  const paths=navigationGroups('teacher').flatMap(g=>g.items).map(i=>i.path)
  for(const path of ['/student/lab-topics','/teacher/lab-topics','/student/simulation-console','/teacher/exercises','/teacher/exercises/new','/student/chapter-bank']) assert.ok(!paths.includes(path))
  for(const path of ['/teacher/chapter-bank','/teacher/grading','/exams/manage','/exams/grading']) assert.ok(paths.includes(path))
  assert.equal(teacherDestination('/student/chapter-bank/3'),'/teacher/chapter-bank')
  assert.equal(teacherDestination('/teacher/exercises/5/edit'),'/teacher/dashboard')
  assert.equal(teacherDestination('/teacher/lab-topics'),'/teacher/grading')
  assert.equal(teacherDestination('/exams/grading'),null)
  assert.equal(pageLabel('/exams/grading','teacher'),'考试批阅')
  assert.equal(navigationGroups('student')[0].items.length,3)
})
test('an explicit false answer and blank variants are preserved in authoring payloads',()=>{
  const form={...emptyChapterQuestion(),kind:'true_false',stem:' 判断题 ',answer:false}
  assert.equal(chapterPayload(form,[]).answer,false)
  form.kind='cell'
  const payload=chapterPayload(form,[{answer:' 锁闭 ',variants:'锁 闭\n\n 锁住 '}])
  assert.deepEqual(payload.answer,['锁闭']);assert.deepEqual(payload.accepted,[['锁 闭','锁住']])
  assert.deepEqual(payload.options,[])
  assert.throws(()=>chapterPayload({...form,stem:' '},[]),/题干/)
  assert.throws(()=>chapterPayload(form,[{answer:'',variants:''}]),/逐空/)
})
test('removing or renumbering an option keeps the intended correct option attached to its text',()=>{
  const form={...emptyChapterQuestion(),options:['甲','乙','丙','丁'],answer:'C'}
  removeChapterOption(form,0);assert.equal(form.answer,'B');assert.equal(form.options[1],'丙')
  removeChapterOption(form,1);assert.equal(form.answer,null)
  const multi={...form,kind:'multi',options:['甲','乙','丙'],answer:['A','C']}
  removeChapterOption(multi,1);assert.deepEqual(multi.answer,['A','B'])
  assert.throws(()=>chapterPayload({...form,stem:'选择题',options:['甲',''],answer:'A'},[]),/所有选项/)
})
