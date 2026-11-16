export const chapterTitles = ['进路选择与设备操作','进路取消与人工解锁','模拟行车与正常解锁','故障现象与安全处理','列车进路联锁表','调车进路联锁表']
export const chapterKinds = {choice:'单选题',multi:'多选题',true_false:'判断题',cell:'填空题'}
export const optionKey = index => String.fromCharCode(65 + index)
export function emptyChapterQuestion() {
  return {chapter:1,kind:'choice',stem:'',options:['','','',''],answer:null,accepted:[],explanation:'',source_reference:'教师自编题'}
}
export function chapterPayload(form, blanks) {
  const payload = {chapter:form.chapter,kind:form.kind,stem:form.stem.trim(),
    options:['choice','multi'].includes(form.kind)?form.options.map(s=>s.trim()):[],
    answer:form.kind==='cell'?blanks.map(b=>b.answer.trim()):form.answer,
    accepted:form.kind==='cell'?blanks.map(b=>b.variants.split('\n').map(s=>s.trim()).filter(Boolean)):[],
    explanation:form.explanation.trim(),source_reference:form.source_reference.trim()}
  if (!payload.stem || !payload.source_reference) throw new Error('请填写题干和命题依据')
  if (['choice','multi'].includes(payload.kind)) {
    if (payload.options.length<2 || payload.options.some(s=>!s)) throw new Error('请填写所有选项，或移除空白选项（至少保留两项）')
    const keys=payload.options.map((_,i)=>optionKey(i))
    if (payload.kind==='choice' && !keys.includes(payload.answer)) throw new Error('请选择一个标准答案')
    if (payload.kind==='multi' && (!Array.isArray(payload.answer) || !payload.answer.length || new Set(payload.answer).size!==payload.answer.length || payload.answer.some(a=>!keys.includes(a)))) throw new Error('请选择有效的多选题标准答案')
  }
  if (payload.kind==='true_false' && typeof payload.answer!=='boolean') throw new Error('请明确选择判断题的正确或错误')
  if (payload.kind==='cell' && (!payload.answer.length || payload.answer.some(s=>!s))) throw new Error('请逐空填写标准答案')
  return payload
}
export function removeChapterOption(form,index) {
  const selected=Array.isArray(form.answer)?form.answer:[form.answer]
  const remaining=form.options.map((text,i)=>({text,key:optionKey(i)})).filter((_,i)=>i!==index)
  form.options=remaining.map(o=>o.text)
  const answers=remaining.flatMap((o,i)=>selected.includes(o.key)?[optionKey(i)]:[])
  form.answer=form.kind==='multi'?answers:answers[0]??null
}
