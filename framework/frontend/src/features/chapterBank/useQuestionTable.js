import { reactive, ref } from 'vue'

export const questionKinds = { choice:'单选题', multi:'多选题', true_false:'判断题', cell:'填空题' }
export function progressText(question) {
  return question.ever_correct ? '做对过' : question.attempted ? '尚未做对' : '暂无答对记录'
}
export function createQuestionTable({ get }) {
  const filters=reactive({chapter:'',kind:'objective',progress:'all',search:''})
  const items=ref([]),total=ref(0),page=ref(1),limit=ref(20),loading=ref(false),error=ref('')
  let version=0,disposed=false
  async function load() {
    if(disposed)return
    const current=++version
    loading.value=true;error.value=''
    try {
      const data=await get('/chapter-bank/questions',{params:{...filters,chapter:filters.chapter || undefined,page:page.value,limit:limit.value}})
      if(disposed || current!==version)return
      items.value=data.items;total.value=data.total
    } catch(failure) {
      if(!disposed && current===version)error.value=typeof failure?.response?.data?.detail==='string'?failure.response.data.detail:'题目加载失败，请重试。'
    } finally { if(!disposed && current===version)loading.value=false }
  }
  function apply() { page.value=1;return load() }
  function setPage(value) { page.value=value;return load() }
  function dispose() { disposed=true;version++ }
  return {filters,items,total,page,limit,loading,error,load,apply,setPage,dispose}
}
