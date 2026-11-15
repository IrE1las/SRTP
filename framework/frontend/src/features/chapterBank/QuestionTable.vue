<template>
  <main class="question-directory">
    <header class="directory-heading"><div><router-link to="/student/chapter-bank">返回章节练习</router-link><h1>全部题目</h1><p>浏览六章客观题，右侧显示当前账号是否曾经答对。</p></div><span>{{ total }} 道题</span></header>
    <form class="directory-filters" @submit.prevent="table.apply">
      <label>章节<el-select v-model="filters.chapter" placeholder="全部章节" aria-label="按章节筛选" @change="table.apply"><el-option label="全部章节" value=""/><el-option v-for="(title,index) in chapterTitles" :key="index" :label="`${index+1} · ${title}`" :value="index+1"/></el-select></label>
      <label>题型<el-select v-model="filters.kind" aria-label="按题型筛选" @change="table.apply"><el-option label="全部题型" value="objective"/><el-option v-for="(title,value) in questionKinds" :key="value" :label="title" :value="value"/></el-select></label>
      <label>答对记录<el-select v-model="filters.progress" aria-label="按答对记录筛选" @change="table.apply"><el-option label="全部记录" value="all"/><el-option label="做对过" value="correct"/><el-option label="从未做对" value="not_correct"/><el-option label="尚未作答" value="unanswered"/></el-select></label>
      <div class="directory-search"><el-input v-model="filters.search" aria-label="搜索题目" placeholder="搜索题目内容" clearable maxlength="150" @clear="table.apply"/><el-button native-type="submit" type="primary">搜索</el-button></div>
    </form>
    <p v-if="error" class="directory-error" role="alert">{{ error }}<button @click="table.load">重新加载</button></p>
    <section class="directory-table" aria-label="全部客观题列表" :aria-busy="loading">
      <p class="swipe-note">表格可左右滑动，右侧查看答对记录。</p>
      <el-table v-loading="loading" :data="items" row-key="id" :empty-text="error?'加载失败，请重试':'没有符合条件的题目'">
        <el-table-column label="章节 / 题型" width="145"><template #default="{row}"><span class="question-chapter">第 {{ row.chapter }} 章</span><small>{{ questionKinds[row.kind] }}</small></template></el-table-column>
        <el-table-column label="题目" min-width="330"><template #default="{row}"><p class="directory-stem">{{ row.stem }}</p><details v-if="row.options?.length || row.images?.length" class="question-material"><summary>查看选项与题图</summary><ol v-if="row.options?.length"><li v-for="option in row.options" :key="option.key"><span>{{ option.key }}.</span> {{ option.text }}</li></ol><a v-for="figure in row.images || []" :key="figure.src" :href="figure.src" target="_blank" rel="noopener"><img :src="figure.src" :alt="figure.alt" loading="lazy"></a></details><span class="question-id">{{ row.id }}</span></template></el-table-column>
        <el-table-column label="是否做对过" width="170" fixed="right"><template #default="{row}"><span :class="['answer-history',{correct:row.ever_correct,attempted:row.attempted&&!row.ever_correct}]">{{ row.ever_correct?'✓ ':'' }}{{ progressText(row) }}</span><small v-if="!row.can_practice">尚未开放判分练习</small><small v-else-if="!row.attempted">尚未作答</small></template></el-table-column>
      </el-table>
      <footer class="directory-footer"><p>未开放练习的题目仍可查看题面，暂不判分。</p><el-pagination :current-page="page" :page-size="limit" :page-sizes="[20,50,100]" :total="total" layout="total, sizes, prev, pager, next" @current-change="table.setPage" @size-change="value=>{limit=value;table.apply()}"/></footer>
    </section>
  </main>
</template>
<script setup>
import { onBeforeUnmount,onMounted } from 'vue'
import request from '@/utils/request'
import { createQuestionTable,questionKinds,progressText } from './useQuestionTable.js'
const chapterTitles=['进路选择与设备操作','进路取消与人工解锁','模拟行车与正常解锁','故障现象与安全处理','列车进路联锁表','调车进路联锁表']
const table=createQuestionTable({get:(url,config)=>request.get(url,config)})
const {filters,items,total,page,limit,loading,error}=table
onMounted(table.load)
onBeforeUnmount(table.dispose)
</script>
<style scoped>
.swipe-note{display:none}@media(max-width:650px){.swipe-note{display:block;margin:0;padding:12px 14px;font-size:12px;color:#708094;background:#f3f7fa}.directory-table :deep(.el-table__cell.el-table-fixed-column--right){position:static}.directory-table :deep(.el-table-fixed-column--right:before){display:none}}
.question-directory{max-width:1400px;margin:auto;color:#19334d}.directory-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:25px}.directory-heading a{font-size:13px}.directory-heading h1{font-size:28px;font-weight:600;margin:14px 0 10px}.directory-heading p{font-size:14px;color:#708094;margin:0;line-height:1.8}.directory-heading>span{font-size:14px;white-space:nowrap;color:#708094}.directory-filters{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;margin-bottom:20px}.directory-filters>label{display:grid;gap:9px;font-size:12px;color:#708094;width:175px}.directory-filters>label:first-child{width:240px}.directory-search{display:flex;gap:9px;flex:1;min-width:240px}.directory-table{border:1px solid #dfe7ee;border-top:3px solid #c6aa70;background:white;border-radius:8px;overflow:hidden}.directory-table :deep(.el-table){--el-table-header-bg-color:#f3f7fa}.directory-table :deep(.el-table .cell){padding:14px 20px;line-height:1.8}.directory-table small{display:block;font-size:11px;color:#899aa9;margin-top:5px}.directory-stem{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;color:#19334d;font-size:14px;line-height:1.9}.question-chapter{font-size:14px}.question-id{display:block;font-size:10px;color:#91a0ac;margin-top:9px}.question-material{font-size:12px;color:#58778d;margin-top:10px}.question-material summary{cursor:pointer;color:#0075b7}.question-material ol{padding:0;list-style:none;line-height:1.9}.question-material li{margin:5px 0}.question-material img{max-width:100%;max-height:250px;object-fit:contain;display:block;margin:12px 0}.answer-history{font-size:13px;color:#7d8c99}.answer-history.correct{color:#287d5f}.answer-history.attempted{color:#b26d3d}.directory-footer{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:20px;flex-wrap:wrap;border-top:1px solid #e6ebf1}.directory-footer p{font-size:12px;color:#899aa9;margin:0}.directory-error{background:#fff1ea;color:#a0593b;padding:14px;font-size:13px}.directory-error button{margin-left:16px;border:0;background:none;color:#0075b7;cursor:pointer}@media(max-width:650px){.directory-heading{align-items:flex-start}.directory-heading h1{font-size:24px}.directory-filters{gap:12px}.directory-filters>label,.directory-filters>label:first-child{width:calc(50% - 6px)}.directory-search{width:100%;flex-basis:100%}.directory-footer{padding:14px}.directory-footer :deep(.el-pagination){max-width:100%;overflow:auto}}
</style>
